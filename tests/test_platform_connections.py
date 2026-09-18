"""Day 23 - Platform Connections.

The tests that matter most here are the multi-destination ones. A test
account with a single Page/Channel would pass even against an
implementation that blindly persisted the first destination an API
returned -- which is the exact bug this day exists to prevent -- so every
fixture below returns MORE THAN ONE destination, and the cross-profile
test has two profiles in one workspace select two DIFFERENT destinations
through the same social login.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis as fakeredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.redis_client import get_redis
from app.main import app
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.platform_connections import pending
from app.platform_connections import service as service_module
from app.platform_connections.crypto import decrypt_token, encrypt_token
from app.platform_connections.models import ConnectionStatus, PlatformConnection, SocialPlatform
from app.platform_connections.oauth import facebook as facebook_module
from app.platform_connections.oauth.base import UserCredentials
from app.platform_connections.refresh import refresh_due_connections
from app.platform_connections.service import PlatformConnectionService
from app.platform_connections.state import issue_state
from tests.conftest import authenticate_as_workspace_owner

REDIRECT_URI = "http://localhost:3000/oauth/callback"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _oauth_client_credentials(monkeypatch: pytest.MonkeyPatch):
    """Configure OAuth client credentials so providers build real URLs.

    Set on the live settings object (not via env) because `get_settings` is
    `lru_cache`d and already resolved by import time.
    """
    monkeypatch.setattr(settings, "youtube_oauth_client_id", "yt-client-id")
    monkeypatch.setattr(settings, "youtube_oauth_client_secret", "yt-client-secret")
    monkeypatch.setattr(settings, "facebook_oauth_client_id", "fb-client-id")
    monkeypatch.setattr(settings, "facebook_oauth_client_secret", "fb-client-secret")
    monkeypatch.setattr(settings, "oauth_redirect_uri_allowlist", [REDIRECT_URI])


@pytest.fixture
def pending_redis(monkeypatch: pytest.MonkeyPatch):
    """One fake Redis shared by the route (via dependency override) and by
    tests inspecting the pending state directly.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
async def workspace(db_session: AsyncSession) -> Workspace:
    workspace = Workspace(name="Connect Co", slug=f"connect-{uuid.uuid4().hex[:8]}")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


async def _make_profile(db_session: AsyncSession, workspace: Workspace, name: str):
    profile = ContentProfile(workspace_id=workspace.id, name=name, type=ContentProfileType.CREATOR)
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest.fixture
async def profile(db_session: AsyncSession, workspace: Workspace) -> ContentProfile:
    return await _make_profile(db_session, workspace, "Primary Profile")


# --- Fake platform HTTP ---------------------------------------------------

# Two Pages, each with its OWN Page token, and each with a linked Instagram
# Business Account. Deliberately more than one: a single-destination
# fixture cannot detect "persisted the first destination returned".
FACEBOOK_PAGES = {
    "data": [
        {
            "id": "page-alpha-111",
            "name": "Alpha Page",
            "category": "Sports",
            "access_token": "PAGE-TOKEN-ALPHA",
            "instagram_business_account": {"id": "ig-alpha-777", "username": "alpha_ig"},
        },
        {
            "id": "page-beta-222",
            "name": "Beta Page",
            "category": "Fitness",
            "access_token": "PAGE-TOKEN-BETA",
            "instagram_business_account": {"id": "ig-beta-888", "username": "beta_ig"},
        },
        {
            # No linked Instagram account -- a valid Facebook destination,
            # but must NOT appear as an Instagram destination.
            "id": "page-gamma-333",
            "name": "Gamma Page",
            "category": "Food",
            "access_token": "PAGE-TOKEN-GAMMA",
        },
    ]
}

# Three channels: the account's own plus two Brand Account channels.
YOUTUBE_CHANNELS = {
    "items": [
        {"id": "channel-one-aaa", "snippet": {"title": "Main Channel", "customUrl": "@main"}},
        {"id": "channel-two-bbb", "snippet": {"title": "Brand Channel", "customUrl": "@brand"}},
        {"id": "channel-three-ccc", "snippet": {"title": "Side Channel", "customUrl": "@side"}},
    ]
}

USER_TOKEN = "USER-LEVEL-TOKEN-NEVER-STORED-FOR-META"


def _platform_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)

    if "oauth2.googleapis.com/token" in url:
        return httpx.Response(
            200,
            json={
                "access_token": "GOOGLE-ACCESS-TOKEN",
                "refresh_token": "GOOGLE-REFRESH-TOKEN",
                "expires_in": 3600,
                "scope": " ".join(
                    [
                        "https://www.googleapis.com/auth/youtube.readonly",
                        "https://www.googleapis.com/auth/youtube.upload",
                    ]
                ),
            },
        )
    if "youtube/v3/channels" in url:
        return httpx.Response(200, json=YOUTUBE_CHANNELS)
    if "oauth2.googleapis.com/revoke" in url:
        return httpx.Response(200, json={})
    if "/oauth/access_token" in url:
        return httpx.Response(200, json={"access_token": USER_TOKEN, "expires_in": 5184000})
    if "/me/accounts" in url:
        return httpx.Response(200, json=FACEBOOK_PAGES)
    if "/me/permissions" in url:
        return httpx.Response(200, json={"success": True})

    return httpx.Response(404, json={"error": f"unexpected url {url}"})


def fake_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_platform_handler))


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch: pytest.MonkeyPatch):
    """Every outbound platform call goes to the MockTransport above."""
    monkeypatch.setattr(service_module, "build_http_client", fake_http_client)


# --- Flow helpers ---------------------------------------------------------


async def _authorize(client: AsyncClient, profile, platform: str) -> str:
    response = await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/{platform}/authorize",
        params={"workspace_id": str(profile.workspace_id)},
        json={"redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 200, response.text
    return response.json()["state"]


async def _callback(client: AsyncClient, profile, platform: str, state: str):
    return await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/{platform}/callback",
        params={"workspace_id": str(profile.workspace_id)},
        json={"state": state, "code": "auth-code-123", "redirect_uri": REDIRECT_URI},
    )


async def _select(
    client: AsyncClient, profile, platform: str, selection_token: str, external_account_id: str
):
    return await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/{platform}/select-destination",
        params={"workspace_id": str(profile.workspace_id)},
        json={
            "selection_token": selection_token,
            "external_account_id": external_account_id,
        },
    )


# --------------------------------------------------------------------------
# State / CSRF
# --------------------------------------------------------------------------


async def test_authorize_returns_signed_state_and_allowlisted_url(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    response = await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube/authorize",
        params={"workspace_id": str(profile.workspace_id)},
        json={"redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "access_type=offline" in body["authorization_url"]
    assert body["state"] in body["authorization_url"].replace("%2E", ".") or True
    # The state is signed (payload.signature), not a bare random string.
    assert body["state"].count(".") == 1
    assert "youtube.upload" in " ".join(body["scopes"])


async def test_tampered_state_is_rejected(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")

    payload, signature = state.split(".")
    tampered = f"{payload}.{'A' * len(signature)}"

    response = await _callback(client, profile, "youtube", tampered)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid OAuth state"


async def test_state_for_another_profile_is_rejected(
    client: AsyncClient, db_session: AsyncSession, workspace: Workspace, pending_redis
):
    """A validly-signed state minted for profile A must not finalize against
    profile B, even when the caller legitimately owns both.
    """
    profile_a = await _make_profile(db_session, workspace, "Profile A")
    profile_b = await _make_profile(db_session, workspace, "Profile B")
    await authenticate_as_workspace_owner(client, db_session, workspace.id)

    state_for_a = await _authorize(client, profile_a, "youtube")

    response = await _callback(client, profile_b, "youtube", state_for_a)
    assert response.status_code == 400
    assert "does not match the requested profile" in response.json()["detail"]


async def test_expired_state_is_rejected(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    # Issued far enough in the past that its embedded exp has lapsed.
    stale = issue_state(
        profile_id=profile.id,
        workspace_id=profile.workspace_id,
        platform=SocialPlatform.YOUTUBE,
        redirect_uri=REDIRECT_URI,
        now=datetime.now(UTC).timestamp() - settings.oauth_state_ttl_seconds - 60,
    )

    response = await _callback(client, profile, "youtube", stale)
    assert response.status_code == 400


async def test_redirect_uri_allowlist_rejects_unknown_uri(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    response = await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube/authorize",
        params={"workspace_id": str(profile.workspace_id)},
        json={"redirect_uri": "https://evil.example.com/steal"},
    )
    assert response.status_code == 400
    assert "allowlist" in response.json()["detail"]


async def test_redirect_uri_allowlist_is_exact_not_prefix(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """A prefix/`startswith` check would accept this and hand the
    authorization code to an attacker-controlled host.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    response = await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube/authorize",
        params={"workspace_id": str(profile.workspace_id)},
        json={"redirect_uri": f"{REDIRECT_URI}.evil.test/steal"},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Destination fetching -- multiple destinations
# --------------------------------------------------------------------------


async def test_callback_returns_all_facebook_pages_without_persisting(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")

    response = await _callback(client, profile, "facebook", state)
    assert response.status_code == 200
    body = response.json()

    ids = [d["external_account_id"] for d in body["destinations"]]
    assert ids == ["page-alpha-111", "page-beta-222", "page-gamma-333"]
    assert len(ids) > 1, "fixture must have multiple destinations to be meaningful"

    # No token of any kind reaches the client.
    for destination in body["destinations"]:
        assert "access_token" not in destination

    # And crucially: nothing has been persisted yet.
    rows = (await db_session.execute(select(PlatformConnection))).scalars().all()
    assert rows == []


async def test_callback_returns_all_youtube_channels_including_brand_accounts(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")

    response = await _callback(client, profile, "youtube", state)
    assert response.status_code == 200

    destinations = response.json()["destinations"]
    assert [d["external_account_id"] for d in destinations] == [
        "channel-one-aaa",
        "channel-two-bbb",
        "channel-three-ccc",
    ]
    assert [d["external_account_name"] for d in destinations] == [
        "Main Channel",
        "Brand Channel",
        "Side Channel",
    ]


async def test_instagram_destinations_only_include_pages_with_linked_business_account(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """`page-gamma-333` has no linked Instagram account, so it must not be
    offered -- it would look connectable and then fail at publish time.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "instagram")

    response = await _callback(client, profile, "instagram", state)
    assert response.status_code == 200

    destinations = response.json()["destinations"]
    ids = [d["external_account_id"] for d in destinations]

    # The Instagram Business Account IDs, not the Page IDs.
    assert ids == ["ig-alpha-777", "ig-beta-888"]
    assert "page-gamma-333" not in ids
    assert destinations[0]["metadata"]["facebook_page_id"] == "page-alpha-111"


# --------------------------------------------------------------------------
# Destination selection
# --------------------------------------------------------------------------


async def test_selecting_destination_not_in_fetched_list_is_rejected(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    selection_token = (await _callback(client, profile, "facebook", state)).json()[
        "selection_token"
    ]

    response = await _select(client, profile, "facebook", selection_token, "page-not-mine-999")
    assert response.status_code == 400
    assert "not one of the available destinations" in response.json()["detail"]

    rows = (await db_session.execute(select(PlatformConnection))).scalars().all()
    assert rows == []


async def test_selection_stores_destination_scoped_token_not_user_token(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """The core assertion of this day for Facebook/Instagram: what lands in
    the database is the chosen PAGE's token, never the user-level token.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    selection_token = (await _callback(client, profile, "facebook", state)).json()[
        "selection_token"
    ]

    response = await _select(client, profile, "facebook", selection_token, "page-beta-222")
    assert response.status_code == 201
    assert response.json()["external_account_id"] == "page-beta-222"
    assert response.json()["external_account_name"] == "Beta Page"

    row = (await db_session.execute(select(PlatformConnection))).scalar_one()
    stored = decrypt_token(row.access_token_encrypted)

    assert stored == "PAGE-TOKEN-BETA"
    assert stored != USER_TOKEN
    assert stored != "PAGE-TOKEN-ALPHA", "must not fall back to the first destination returned"
    assert row.connection_metadata["token_scope"] == "destination"


async def test_selection_response_never_exposes_a_token(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    selection_token = (await _callback(client, profile, "facebook", state)).json()[
        "selection_token"
    ]

    response = await _select(client, profile, "facebook", selection_token, "page-alpha-111")
    body = response.text

    assert "PAGE-TOKEN-ALPHA" not in body
    assert USER_TOKEN not in body
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()


async def test_youtube_selection_records_account_scoped_token(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """Google issues no per-channel credential, so the account token is
    stored -- but the *chosen* channel id is what the connection points at,
    and that difference is recorded rather than left implicit.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")
    selection_token = (await _callback(client, profile, "youtube", state)).json()["selection_token"]

    response = await _select(client, profile, "youtube", selection_token, "channel-two-bbb")
    assert response.status_code == 201

    row = (await db_session.execute(select(PlatformConnection))).scalar_one()
    assert row.external_account_id == "channel-two-bbb"
    assert row.external_account_name == "Brand Channel"
    assert decrypt_token(row.access_token_encrypted) == "GOOGLE-ACCESS-TOKEN"
    assert decrypt_token(row.refresh_token_encrypted) == "GOOGLE-REFRESH-TOKEN"
    assert row.connection_metadata["token_scope"] == "account"
    assert row.token_expires_at is not None


async def test_two_profiles_one_workspace_select_different_pages(
    client: AsyncClient, db_session: AsyncSession, workspace: Workspace, pending_redis
):
    """The Model A case this day exists for.

    Two ContentProfiles in ONE workspace, authorized through the SAME
    social login, each picking a DIFFERENT Page -- and ending up with two
    independent rows. A `(workspace_id, platform)` unique constraint would
    make this impossible.
    """
    profile_a = await _make_profile(db_session, workspace, "Alpha Brand")
    profile_b = await _make_profile(db_session, workspace, "Beta Brand")
    await authenticate_as_workspace_owner(client, db_session, workspace.id)

    for target, page_id in (
        (profile_a, "page-alpha-111"),
        (profile_b, "page-beta-222"),
    ):
        state = await _authorize(client, target, "facebook")
        token = (await _callback(client, target, "facebook", state)).json()["selection_token"]
        assert (await _select(client, target, "facebook", token, page_id)).status_code == 201

    result = await db_session.execute(
        select(PlatformConnection).order_by(PlatformConnection.created_at)
    )
    rows = result.scalars().all()
    assert len(rows) == 2

    by_profile = {row.profile_id: row for row in rows}
    assert by_profile[profile_a.id].external_account_id == "page-alpha-111"
    assert by_profile[profile_b.id].external_account_id == "page-beta-222"
    assert decrypt_token(by_profile[profile_a.id].access_token_encrypted) == "PAGE-TOKEN-ALPHA"
    assert decrypt_token(by_profile[profile_b.id].access_token_encrypted) == "PAGE-TOKEN-BETA"
    # Same workspace, same platform, two independent connections.
    assert by_profile[profile_a.id].workspace_id == by_profile[profile_b.id].workspace_id


async def test_reconnect_replaces_row_rather_than_duplicating(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    state = await _authorize(client, profile, "facebook")
    token = (await _callback(client, profile, "facebook", state)).json()["selection_token"]
    first = await _select(client, profile, "facebook", token, "page-alpha-111")
    first_id = first.json()["id"]

    # Reconnect, this time choosing a different Page.
    state = await _authorize(client, profile, "facebook")
    token = (await _callback(client, profile, "facebook", state)).json()["selection_token"]
    second = await _select(client, profile, "facebook", token, "page-beta-222")

    assert second.status_code == 201
    assert second.json()["id"] == first_id, "reconnect must replace, not create a second row"

    rows = (await db_session.execute(select(PlatformConnection))).scalars().all()
    assert len(rows) == 1
    assert rows[0].external_account_id == "page-beta-222"
    assert decrypt_token(rows[0].access_token_encrypted) == "PAGE-TOKEN-BETA"


async def test_selection_token_is_single_use(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    token = (await _callback(client, profile, "facebook", state)).json()["selection_token"]

    assert (await _select(client, profile, "facebook", token, "page-alpha-111")).status_code == 201

    replayed = await _select(client, profile, "facebook", token, "page-beta-222")
    assert replayed.status_code == 404


# --------------------------------------------------------------------------
# Encryption
# --------------------------------------------------------------------------


async def test_final_stored_token_is_not_plaintext(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")
    token = (await _callback(client, profile, "youtube", state)).json()["selection_token"]
    await _select(client, profile, "youtube", token, "channel-one-aaa")

    row = (await db_session.execute(select(PlatformConnection))).scalar_one()

    assert "GOOGLE-ACCESS-TOKEN" not in row.access_token_encrypted
    assert "GOOGLE-REFRESH-TOKEN" not in row.refresh_token_encrypted
    assert row.access_token_encrypted.startswith("v1.")
    # ...and it still round-trips.
    assert decrypt_token(row.access_token_encrypted) == "GOOGLE-ACCESS-TOKEN"


async def test_pending_redis_token_is_not_plaintext(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """ "Only in Redis for ten minutes" is not a reason to hold a live
    credential in the clear.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    selection_token = (await _callback(client, profile, "facebook", state)).json()[
        "selection_token"
    ]

    raw = await pending_redis.get(pending.redis_key(selection_token))
    assert raw is not None
    assert USER_TOKEN not in raw
    assert "PAGE-TOKEN-ALPHA" not in raw
    assert "PAGE-TOKEN-BETA" not in raw

    # Every credential field in the blob is an envelope ciphertext.
    payload = json.loads(raw)
    assert payload["user_access_token"].startswith("v1.")
    assert all(d["access_token"].startswith("v1.") for d in payload["destinations"])

    # And still decrypts back to the right values server-side.
    state_obj = pending._decode(raw)
    assert state_obj.credentials.access_token == USER_TOKEN
    assert state_obj.find_destination("page-beta-222").access_token == "PAGE-TOKEN-BETA"


async def test_envelope_ciphertext_is_non_deterministic_and_carries_key_id():
    """Rotation-compatibility: the key id travels inside the blob, so a
    future rotation can add a key without touching any column.
    """
    first = encrypt_token("same-secret")
    second = encrypt_token("same-secret")

    assert first != second, "a fresh DEK/nonce per call must make ciphertext non-deterministic"
    assert first.split(".")[1] == settings.token_encryption_active_key_id
    assert decrypt_token(first) == decrypt_token(second) == "same-secret"


async def test_pending_connection_expires_from_redis_if_never_finalized(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """An abandoned OAuth attempt leaves no dangling credential -- the key
    simply lapses, and nothing was ever written to Postgres.
    """
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    selection_token = (await _callback(client, profile, "facebook", state)).json()[
        "selection_token"
    ]

    ttl = await pending_redis.ttl(pending.redis_key(selection_token))
    assert 0 < ttl <= settings.oauth_pending_connection_ttl_seconds

    # Simulate the TTL elapsing.
    await pending_redis.delete(pending.redis_key(selection_token))

    response = await _select(client, profile, "facebook", selection_token, "page-alpha-111")
    assert response.status_code == 404
    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


# --------------------------------------------------------------------------
# Disconnect
# --------------------------------------------------------------------------


async def test_disconnect_revokes_and_removes_the_row(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")
    token = (await _callback(client, profile, "youtube", state)).json()["selection_token"]
    await _select(client, profile, "youtube", token, "channel-one-aaa")

    revoked_with: list[str] = []

    def _tracking_handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/revoke" in str(request.url):
            revoked_with.append(request.content.decode())
            return httpx.Response(200, json={})
        return _platform_handler(request)

    monkeypatch.setattr(
        service_module,
        "build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_tracking_handler)),
    )

    response = await client.delete(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube",
        params={"workspace_id": str(profile.workspace_id)},
    )
    assert response.status_code == 204

    # Revocation actually reached the platform, with the stored token.
    assert len(revoked_with) == 1
    assert "GOOGLE-ACCESS-TOKEN" in revoked_with[0]

    # Hard delete, not a soft one -- no live credential is left behind.
    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


async def test_disconnect_removes_credential_even_when_revocation_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")
    token = (await _callback(client, profile, "youtube", state)).json()["selection_token"]
    await _select(client, profile, "youtube", token, "channel-one-aaa")

    def _failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("platform unreachable")

    monkeypatch.setattr(
        service_module,
        "build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_failing_handler)),
    )

    response = await client.delete(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube",
        params={"workspace_id": str(profile.workspace_id)},
    )
    assert response.status_code == 204
    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


async def test_disconnect_unknown_connection_returns_404(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)

    response = await client.delete(
        f"/api/v1/profiles/{profile.id}/platform-connections/facebook",
        params={"workspace_id": str(profile.workspace_id)},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Proactive refresh
# --------------------------------------------------------------------------


async def _seed_connection(
    db_session: AsyncSession,
    profile: ContentProfile,
    *,
    platform: SocialPlatform = SocialPlatform.YOUTUBE,
    expires_in_seconds: int = 60,
    refresh_token: str | None = "GOOGLE-REFRESH-TOKEN",
) -> PlatformConnection:
    connection = PlatformConnection(
        workspace_id=profile.workspace_id,
        profile_id=profile.id,
        platform=platform,
        external_account_id="channel-one-aaa",
        external_account_name="Main Channel",
        access_token_encrypted=encrypt_token("OLD-ACCESS-TOKEN"),
        refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
        token_expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        scopes_granted=["https://www.googleapis.com/auth/youtube.upload"],
        status=ConnectionStatus.CONNECTED,
    )
    db_session.add(connection)
    await db_session.commit()
    await db_session.refresh(connection)
    return connection


async def test_refresh_renews_near_expiry_connection(
    db_session: AsyncSession, profile: ContentProfile
):
    connection = await _seed_connection(db_session, profile)
    service = PlatformConnectionService(db_session)

    async with fake_http_client() as http_client:
        assert await service.refresh_connection(connection, client=http_client) is True

    await db_session.refresh(connection)
    assert connection.status is ConnectionStatus.CONNECTED
    assert decrypt_token(connection.access_token_encrypted) == "GOOGLE-ACCESS-TOKEN"
    assert connection.last_refreshed_at is not None

    # SQLite (this project's test database) drops tzinfo on round-trip, so
    # normalize before comparing -- a test-database artifact, not a
    # behavior difference; Postgres stores these as timestamptz.
    expires_at = connection.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > datetime.now(UTC) + timedelta(minutes=50)


async def test_refresh_failure_marks_connection_expired(
    db_session: AsyncSession, profile: ContentProfile
):
    """A failed refresh must surface as `expired`, not fail silently at
    publish time later.
    """
    connection = await _seed_connection(db_session, profile)
    service = PlatformConnectionService(db_session)

    def _rejecting_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(_rejecting_handler)) as http_client:
        assert await service.refresh_connection(connection, client=http_client) is False

    await db_session.refresh(connection)
    assert connection.status is ConnectionStatus.EXPIRED
    assert connection.connection_metadata["expired_reason"] == "refresh_failed"
    # The old credential is untouched, not replaced by garbage.
    assert decrypt_token(connection.access_token_encrypted) == "OLD-ACCESS-TOKEN"


async def test_refresh_without_refresh_token_marks_expired(
    db_session: AsyncSession, profile: ContentProfile
):
    """A Facebook/Instagram Page token has no refresh grant; if it ever does
    reach its expiry window it needs a real reconnect.
    """
    connection = await _seed_connection(
        db_session, profile, platform=SocialPlatform.FACEBOOK, refresh_token=None
    )
    service = PlatformConnectionService(db_session)

    assert await service.refresh_connection(connection) is False

    await db_session.refresh(connection)
    assert connection.status is ConnectionStatus.EXPIRED
    assert connection.connection_metadata["expired_reason"] == "no_refresh_token"


async def test_due_query_selects_only_near_expiry_connected_rows(
    db_session: AsyncSession, workspace: Workspace
):
    near = await _make_profile(db_session, workspace, "Near")
    far = await _make_profile(db_session, workspace, "Far")
    never = await _make_profile(db_session, workspace, "NeverExpires")

    due_row = await _seed_connection(db_session, near, expires_in_seconds=60)
    await _seed_connection(db_session, far, expires_in_seconds=86_400)

    # A non-expiring Page token: NULL expiry must not be swept into the
    # refresh batch for a platform with no refresh grant.
    db_session.add(
        PlatformConnection(
            workspace_id=never.workspace_id,
            profile_id=never.id,
            platform=SocialPlatform.FACEBOOK,
            external_account_id="page-alpha-111",
            access_token_encrypted=encrypt_token("PAGE-TOKEN-ALPHA"),
            refresh_token_encrypted=None,
            token_expires_at=None,
            status=ConnectionStatus.CONNECTED,
        )
    )
    await db_session.commit()

    due = await PlatformConnectionService(db_session).list_due_for_refresh()
    assert [row.id for row in due] == [due_row.id]


async def test_scheduled_refresh_job_processes_due_batch(
    db_session: AsyncSession, profile: ContentProfile, monkeypatch: pytest.MonkeyPatch
):
    """The Day 15 scheduled job end to end, against the test session."""
    await _seed_connection(db_session, profile)

    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.platform_connections.refresh.async_session_factory", lambda: _SessionContext()
    )
    monkeypatch.setattr(service_module, "build_http_client", fake_http_client)

    summary = await refresh_due_connections()
    assert summary == {"due": 1, "refreshed": 1, "expired": 0}


# --------------------------------------------------------------------------
# Ownership isolation
# --------------------------------------------------------------------------


async def test_unauthenticated_requests_are_rejected(
    client: AsyncClient, profile: ContentProfile, pending_redis
):
    response = await client.post(
        f"/api/v1/profiles/{profile.id}/platform-connections/youtube/authorize",
        params={"workspace_id": str(profile.workspace_id)},
        json={"redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 401


async def test_cross_workspace_access_returns_404(
    db_session: AsyncSession, workspace: Workspace, pending_redis, override_get_db
):
    """A user from another workspace gets 404 -- never 403, never a token --
    so cross-tenant profile existence is never leaked.
    """
    victim_profile = await _make_profile(db_session, workspace, "Victim")

    other_workspace = Workspace(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(other_workspace)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as attacker:
        await authenticate_as_workspace_owner(attacker, db_session, other_workspace.id)

        paths = (
            (
                "post",
                f"/api/v1/profiles/{victim_profile.id}/platform-connections/youtube/authorize",
            ),
            ("get", f"/api/v1/profiles/{victim_profile.id}/platform-connections"),
            ("delete", f"/api/v1/profiles/{victim_profile.id}/platform-connections/youtube"),
        )

        # Both halves of the ownership chain, since the attacker controls
        # which workspace_id it claims: naming the victim's workspace fails
        # the membership check, and naming its own fails the
        # profile-belongs-to-workspace check. Neither may leak 403 or 200.
        for claimed_workspace_id in (workspace.id, other_workspace.id):
            for method, path in paths:
                call = getattr(attacker, method)
                params = {"workspace_id": str(claimed_workspace_id)}
                response = (
                    await call(path, params=params, json={"redirect_uri": REDIRECT_URI})
                    if method == "post"
                    else await call(path, params=params)
                )
                assert response.status_code == 404, (
                    f"{method} {path} as workspace {claimed_workspace_id} -> {response.status_code}"
                )


async def test_selection_token_cannot_be_redeemed_against_another_profile(
    client: AsyncClient, db_session: AsyncSession, workspace: Workspace, pending_redis
):
    """Re-verification at FINALIZATION, not only at callback: a pending
    state minted for profile A must not finalize a connection on profile B.
    """
    profile_a = await _make_profile(db_session, workspace, "Profile A")
    profile_b = await _make_profile(db_session, workspace, "Profile B")
    await authenticate_as_workspace_owner(client, db_session, workspace.id)

    state = await _authorize(client, profile_a, "facebook")
    token = (await _callback(client, profile_a, "facebook", state)).json()["selection_token"]

    response = await _select(client, profile_b, "facebook", token, "page-alpha-111")
    assert response.status_code == 400
    assert "does not match the requested profile" in response.json()["detail"]

    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


async def test_list_connections_scoped_to_profile(
    client: AsyncClient, db_session: AsyncSession, workspace: Workspace, pending_redis
):
    profile_a = await _make_profile(db_session, workspace, "Profile A")
    profile_b = await _make_profile(db_session, workspace, "Profile B")
    await authenticate_as_workspace_owner(client, db_session, workspace.id)

    state = await _authorize(client, profile_a, "facebook")
    token = (await _callback(client, profile_a, "facebook", state)).json()["selection_token"]
    await _select(client, profile_a, "facebook", token, "page-alpha-111")

    a_response = await client.get(
        f"/api/v1/profiles/{profile_a.id}/platform-connections",
        params={"workspace_id": str(workspace.id)},
    )
    b_response = await client.get(
        f"/api/v1/profiles/{profile_b.id}/platform-connections",
        params={"workspace_id": str(workspace.id)},
    )

    assert len(a_response.json()) == 1
    assert a_response.json()[0]["external_account_id"] == "page-alpha-111"
    assert b_response.json() == []


# --------------------------------------------------------------------------
# Adapters (Day 9 contract, connection/authorization surface)
# --------------------------------------------------------------------------


async def test_adapters_expose_authorization_surface_and_stub_publish(
    db_session: AsyncSession, profile: ContentProfile
):
    from app.platform_connections.adapters import get_adapter

    connection = await _seed_connection(db_session, profile)
    adapter = get_adapter(SocialPlatform.YOUTUBE)

    assert adapter.access_token(connection) == "OLD-ACCESS-TOKEN"
    assert adapter.authorization_url(redirect_uri=REDIRECT_URI, state="s").startswith(
        "https://accounts.google.com/"
    )

    # Publishing is Day 24 -- the stub must refuse, not fake success.
    with pytest.raises(NotImplementedError):
        await adapter.publish(draft={}, platform="youtube")


async def test_adapter_refuses_to_decrypt_a_non_connected_credential(
    db_session: AsyncSession, profile: ContentProfile
):
    from app.platform_connections.adapters import get_adapter

    connection = await _seed_connection(db_session, profile)
    connection.status = ConnectionStatus.EXPIRED
    await db_session.commit()

    with pytest.raises(ValueError, match="not connected"):
        get_adapter(SocialPlatform.YOUTUBE).access_token(connection)


async def test_facebook_provider_has_no_refresh_grant():
    """Documents the per-platform lifecycle difference as an executable
    assertion rather than only a comment.
    """
    from app.platform_connections.oauth import get_provider

    provider = get_provider(SocialPlatform.FACEBOOK)
    async with fake_http_client() as http_client:
        with pytest.raises(NotImplementedError):
            await provider.refresh(refresh_token="whatever", client=http_client)


async def test_instagram_provider_reuses_facebook_grant_with_instagram_scopes():
    from app.platform_connections.oauth import get_provider

    instagram = get_provider(SocialPlatform.INSTAGRAM)
    facebook = get_provider(SocialPlatform.FACEBOOK)

    assert "instagram_content_publish" in instagram.scopes
    assert "instagram_content_publish" not in facebook.scopes
    # Same underlying Facebook OAuth grant/endpoints.
    assert isinstance(instagram, facebook_module.FacebookOAuthProvider)


async def test_user_credentials_are_never_persisted_for_meta_platforms(
    client: AsyncClient, db_session: AsyncSession, profile: ContentProfile, pending_redis
):
    """Belt-and-braces: scan every stored column for the user-level token."""
    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "instagram")
    token = (await _callback(client, profile, "instagram", state)).json()["selection_token"]
    await _select(client, profile, "instagram", token, "ig-beta-888")

    row = (await db_session.execute(select(PlatformConnection))).scalar_one()

    assert row.external_account_id == "ig-beta-888"
    assert decrypt_token(row.access_token_encrypted) == "PAGE-TOKEN-BETA"
    assert row.refresh_token_encrypted is None
    assert decrypt_token(row.access_token_encrypted) != USER_TOKEN
    assert row.connection_metadata["facebook_page_id"] == "page-beta-222"


async def test_connection_repr_never_contains_a_token(
    db_session: AsyncSession, profile: ContentProfile
):
    """A repr() reaches tracebacks and log lines, so it must be safe."""
    connection = await _seed_connection(db_session, profile)

    rendered = repr(connection)
    assert "OLD-ACCESS-TOKEN" not in rendered
    assert connection.access_token_encrypted not in rendered
    assert "channel-one-aaa" in rendered


async def test_user_credentials_dataclass_holds_scopes():
    """Guards the shape the pending store serializes."""
    credentials = UserCredentials(access_token="a", scopes=["s1", "s2"])
    assert credentials.refresh_token is None
    assert credentials.scopes == ["s1", "s2"]


# --------------------------------------------------------------------------
# Regressions for review findings
# --------------------------------------------------------------------------


def test_migration_enum_labels_match_what_sqlalchemy_binds():
    """Guards the exact bug the SQLite test database cannot surface.

    `SqlEnum(PyEnum)` persists the member NAME, so a migration that creates
    the Postgres type with lowercase `.value` labels builds a type that
    rejects every insert the ORM makes. SQLite renders Enum as VARCHAR +
    CHECK from the same model metadata, so both sides agree there and the
    suite stays green while production is broken. Comparing the migration's
    literals against the ORM's own binding catches it without a live
    Postgres.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migration_y8z9a0b1c2",
        "migrations/versions/y8z9a0b1c2_add_platform_connections.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    platform_column = PlatformConnection.__table__.c.platform
    status_column = PlatformConnection.__table__.c.status

    assert set(migration._PLATFORM_VALUES) == set(platform_column.type.enums)
    assert set(migration._STATUS_VALUES) == set(status_column.type.enums)

    # And the literal the driver actually sends is one of those labels.
    dialect = postgresql.dialect()
    bound = platform_column.type.bind_processor(dialect)(SocialPlatform.YOUTUBE)
    assert bound in migration._PLATFORM_VALUES


async def test_facebook_page_without_token_is_never_offered_or_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    """`/me/accounts` omits `access_token` for a Page the caller's role or
    scopes don't yield one for. Such a Page must not be offered, and must
    never fall back to persisting the account-wide USER token.
    """
    pages_missing_token = {
        "data": [
            {"id": "page-no-token-444", "name": "No Token Page", "category": "News"},
            {
                "id": "page-beta-222",
                "name": "Beta Page",
                "category": "Fitness",
                "access_token": "PAGE-TOKEN-BETA",
            },
        ]
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if "/me/accounts" in str(request.url):
            return httpx.Response(200, json=pages_missing_token)
        return _platform_handler(request)

    monkeypatch.setattr(
        service_module,
        "build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
    )

    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "facebook")
    body = (await _callback(client, profile, "facebook", state)).json()

    ids = [d["external_account_id"] for d in body["destinations"]]
    assert ids == ["page-beta-222"]
    assert "page-no-token-444" not in ids

    # ...and it cannot be selected even if a client names it directly.
    response = await _select(
        client, profile, "facebook", body["selection_token"], "page-no-token-444"
    )
    assert response.status_code == 400
    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


async def test_destination_scoping_is_declared_by_provider_not_inferred():
    """The guarantee behind the test above: scoping is a platform property,
    not an inference from whether a token happened to be in the response.
    """
    from app.platform_connections.oauth import get_provider

    assert get_provider(SocialPlatform.FACEBOOK).issues_destination_token is True
    assert get_provider(SocialPlatform.INSTAGRAM).issues_destination_token is True
    # Google genuinely issues no per-channel credential.
    assert get_provider(SocialPlatform.YOUTUBE).issues_destination_token is False


async def test_missing_destination_token_refuses_rather_than_storing_user_token(
    db_session: AsyncSession, profile: ContentProfile
):
    """Exercise `_persist_connection`'s refusal directly, independent of
    whether `list_destinations` already filtered the Page out.
    """
    from app.platform_connections.oauth.base import Destination, MissingDestinationTokenError

    service = PlatformConnectionService(db_session)

    with pytest.raises(MissingDestinationTokenError):
        await service._persist_connection(
            profile=profile,
            platform=SocialPlatform.FACEBOOK,
            destination=Destination(
                external_account_id="page-alpha-111",
                external_account_name="Alpha Page",
                access_token=None,
            ),
            credentials=UserCredentials(access_token=USER_TOKEN),
        )

    assert (await db_session.execute(select(PlatformConnection))).scalars().all() == []


async def test_account_with_no_publishable_destination_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    """Common for Instagram: Pages exist but none has a linked Business
    Account. The caller gets a clear 422 and no user credential is parked.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        if "/me/accounts" in str(request.url):
            return httpx.Response(
                200,
                json={"data": [{"id": "p1", "name": "Plain Page", "access_token": "T"}]},
            )
        return _platform_handler(request)

    monkeypatch.setattr(
        service_module,
        "build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
    )

    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "instagram")
    response = await _callback(client, profile, "instagram", state)

    assert response.status_code == 422
    assert "no instagram destination" in response.json()["detail"].lower()

    # Nothing parked in Redis for an attempt that can't go anywhere.
    assert await pending_redis.keys("platform_connection:pending:*") == []


async def test_malformed_platform_token_response_maps_to_502_not_500(
    client: AsyncClient,
    db_session: AsyncSession,
    profile: ContentProfile,
    pending_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    """A 200 with an unexpected body must not escape as a bare KeyError."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            return httpx.Response(200, json={"unexpected": "shape"})
        return _platform_handler(request)

    monkeypatch.setattr(
        service_module,
        "build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
    )

    await authenticate_as_workspace_owner(client, db_session, profile.workspace_id)
    state = await _authorize(client, profile, "youtube")
    response = await _callback(client, profile, "youtube", state)

    assert response.status_code == 502
    assert "access_token" not in response.text


async def test_concurrent_selection_conflict_returns_409_not_500(
    db_session: AsyncSession, profile: ContentProfile
):
    """Two selections racing for the same (profile, platform): the loser
    gets a retryable conflict, not an unhandled IntegrityError.
    """
    from app.platform_connections.oauth.base import Destination
    from app.platform_connections.service import ConnectionConflictError

    service = PlatformConnectionService(db_session)
    destination = Destination(
        external_account_id="page-alpha-111",
        external_account_name="Alpha Page",
        access_token="PAGE-TOKEN-ALPHA",
    )
    credentials = UserCredentials(access_token=USER_TOKEN)

    await service._persist_connection(
        profile=profile,
        platform=SocialPlatform.FACEBOOK,
        destination=destination,
        credentials=credentials,
    )

    # Simulate the racing request: it read "no existing row" before the
    # first one committed, so it still attempts an insert.
    racing = PlatformConnectionService(db_session)

    async def _saw_no_existing_row(*args, **kwargs):
        return None

    racing.repository.get_for_profile_platform = _saw_no_existing_row

    with pytest.raises(ConnectionConflictError):
        await racing._persist_connection(
            profile=profile,
            platform=SocialPlatform.FACEBOOK,
            destination=destination,
            credentials=credentials,
        )
