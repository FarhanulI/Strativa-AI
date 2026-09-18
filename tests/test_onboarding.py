from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile

_IDENTITY_PAYLOAD = {
    "name": "Tactics Talk",
    "positioning": "Football tactics explained simply",
    "primary_niche": "football tactics",
    "topics": ["tactics", "analysis"],
    "expertise": ["coaching badges"],
}
_AUDIENCE_PAYLOAD = {
    "target_audience_description": "Casual football fans who want to understand tactics",
    "interests": ["football", "coaching"],
    "pain_points": ["Don't understand formations"],
    "questions": ["Why does a false 9 work?"],
}
_GOALS_PAYLOAD = {"goals": ["growth", "authority"]}
_BRAND_PAYLOAD = {
    "tone": ["energetic", "clear"],
    "style": "short, punchy sentences",
    "things_to_avoid": ["jargon without explanation"],
}
_PLATFORMS_PAYLOAD = {"platforms": ["instagram", "youtube"]}


async def _register(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token


async def test_unauthenticated_onboarding_request_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/onboarding")
    assert response.status_code == 401


async def test_identity_step_creates_profile_and_marks_in_progress(
    client: AsyncClient,
) -> None:
    await _register(client, "identity@example.com")

    response = await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Tactics Talk"
    assert body["primary_niche"] == "football tactics"

    status_response = await client.get("/api/v1/onboarding")
    assert status_response.json()["onboarding_status"] == "in_progress"


async def test_out_of_order_audience_step_rejected_before_identity(
    client: AsyncClient,
) -> None:
    await _register(client, "outoforder@example.com")

    response = await client.put("/api/v1/onboarding/audience", json=_AUDIENCE_PAYLOAD)

    assert response.status_code == 400


async def test_resubmitting_identity_updates_in_place_without_duplicate_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register(client, "resubmit@example.com")

    first = await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)
    assert first.status_code == 200
    profile_id = first.json()["profile_id"]

    updated_payload = dict(_IDENTITY_PAYLOAD, name="Tactics Talk Updated")
    second = await client.put("/api/v1/onboarding/identity", json=updated_payload)
    assert second.status_code == 200
    assert second.json()["profile_id"] == profile_id
    assert second.json()["name"] == "Tactics Talk Updated"

    profiles = (await db_session.execute(select(ContentProfile))).scalars().all()
    assert len(profiles) == 1


async def test_full_step_wise_flow_and_complete(client: AsyncClient) -> None:
    await _register(client, "fullflow@example.com")

    identity_response = await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)
    assert identity_response.status_code == 200

    audience_response = await client.put("/api/v1/onboarding/audience", json=_AUDIENCE_PAYLOAD)
    assert audience_response.status_code == 200
    assert audience_response.json()["pain_points"] == ["Don't understand formations"]

    goals_response = await client.put("/api/v1/onboarding/goals", json=_GOALS_PAYLOAD)
    assert goals_response.status_code == 200
    assert set(goals_response.json()["goals"]) == {"growth", "authority"}

    brand_response = await client.put("/api/v1/onboarding/brand", json=_BRAND_PAYLOAD)
    assert brand_response.status_code == 200
    assert brand_response.json()["style"] == "short, punchy sentences"

    platforms_response = await client.put("/api/v1/onboarding/platforms", json=_PLATFORMS_PAYLOAD)
    assert platforms_response.status_code == 200
    assert set(platforms_response.json()["platforms"]) == {"instagram", "youtube"}

    complete_response = await client.post("/api/v1/onboarding/complete")
    assert complete_response.status_code == 200
    complete_body = complete_response.json()
    assert complete_body["onboarding_status"] == "completed"
    assert complete_body["profile"]["name"] == "Tactics Talk"

    status_response = await client.get("/api/v1/onboarding")
    assert status_response.json()["onboarding_status"] == "completed"


async def test_complete_rejects_when_required_fields_missing(client: AsyncClient) -> None:
    await _register(client, "incomplete@example.com")
    await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)

    response = await client.post("/api/v1/onboarding/complete")

    assert response.status_code == 400
    assert "missing" in response.json()["detail"]


async def test_resumed_session_sees_prior_partial_data(client: AsyncClient) -> None:
    await _register(client, "resume@example.com")
    await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)
    await client.put("/api/v1/onboarding/audience", json=_AUDIENCE_PAYLOAD)

    response = await client.get("/api/v1/onboarding")

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_status"] == "in_progress"
    assert body["identity"]["name"] == "Tactics Talk"
    assert body["audience"]["target_audience_description"].startswith("Casual football fans")


async def test_business_context_never_populated_by_onboarding(client: AsyncClient) -> None:
    await _register(client, "nobusiness@example.com")
    await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)
    await client.put("/api/v1/onboarding/audience", json=_AUDIENCE_PAYLOAD)
    await client.put("/api/v1/onboarding/goals", json=_GOALS_PAYLOAD)
    await client.put("/api/v1/onboarding/brand", json=_BRAND_PAYLOAD)
    await client.put("/api/v1/onboarding/platforms", json=_PLATFORMS_PAYLOAD)

    complete_response = await client.post("/api/v1/onboarding/complete")

    assert complete_response.status_code == 200
    profile = complete_response.json()["profile"]
    business_context_response = await client.get(
        f"/api/v1/profiles/{profile['id']}/business-context",
        params={"workspace_id": profile["workspace_id"]},
    )
    assert business_context_response.status_code == 404


async def test_cross_user_isolation_on_onboarding(client: AsyncClient) -> None:
    await _register(client, "usera@example.com")
    await client.put("/api/v1/onboarding/identity", json=_IDENTITY_PAYLOAD)

    await _register(client, "userb@example.com")
    response = await client.get("/api/v1/onboarding")

    assert response.status_code == 200
    assert response.json()["identity"] is None
    assert response.json()["onboarding_status"] == "not_started"
