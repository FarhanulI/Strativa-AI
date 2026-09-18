"""Request/response contracts for the platform-connection endpoints.

No schema here has a token field of any kind. `PlatformConnectionResponse`
is built from a `PlatformConnection` row whose `access_token_encrypted`/
`refresh_token_encrypted` columns are simply never mapped -- a credential
cannot leak through a response by omission-by-accident, because there is no
field to populate.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.platform_connections.models import ConnectionStatus, SocialPlatform


class AuthorizeRequest(BaseModel):
    redirect_uri: str = Field(
        description=(
            "Where the platform sends the user back. Must match an entry in "
            "`oauth_redirect_uri_allowlist` exactly."
        )
    )


class AuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
    platform: SocialPlatform
    scopes: list[str]


class OAuthCallbackRequest(BaseModel):
    state: str
    code: str
    redirect_uri: str


class AvailableDestination(BaseModel):
    """One Page/Channel the authenticated account can publish to.

    Deliberately carries no `access_token`: the per-destination Page token
    stays in the encrypted Redis pending state and is resolved server-side
    at selection, so it never transits to the client.
    """

    external_account_id: str
    external_account_name: str | None = None
    metadata: dict = Field(default_factory=dict)


class OAuthCallbackResponse(BaseModel):
    """The destination-selection prompt.

    No `PlatformConnection` exists at this point -- this response exists
    precisely so the caller can say which destination it wants before one
    is created.
    """

    selection_token: str
    expires_in_seconds: int
    platform: SocialPlatform
    profile_id: UUID
    destinations: list[AvailableDestination]


class DestinationSelectionRequest(BaseModel):
    selection_token: str
    external_account_id: str


class PlatformConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    profile_id: UUID
    platform: SocialPlatform
    external_account_id: str
    external_account_name: str | None
    token_expires_at: datetime | None
    scopes_granted: list[str] | None
    status: ConnectionStatus
    connected_at: datetime
    last_refreshed_at: datetime | None
    created_at: datetime
    updated_at: datetime
