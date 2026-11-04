"""Per-request credential handling (PRD-21309 AC2, AC7).

Credentials travel only in request headers and only live in a `ContextVar`
for the lifetime of that request (SOP S3.3/S3.4). There is no global or
module-level variable holding a credential anywhere in this codebase -- that
is the one thing a concurrency test (tests/test_middleware.py) must keep
proving, because a regression here is a cross-tenant data leak, not a bug.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from intercom_mcp.errors import not_configured_envelope
from intercom_mcp.settings import DEFAULT_REGION, INTERCOM_REGION_HOSTS

ACCESS_TOKEN_HEADER = "X-Intercom-Access-Token"
REGION_HEADER = "X-Intercom-Region"


@dataclass(frozen=True)
class IntercomCredentials:
    access_token: str
    region: str


_credentials: ContextVar[IntercomCredentials | None] = ContextVar(
    "intercom_credentials", default=None
)


def current_credentials() -> IntercomCredentials | None:
    """None means no request is in flight on this task, or the required
    header was missing (the ASGI middleware already short-circuited that
    case before any tool runs)."""
    return _credentials.get()


@contextmanager
def credentials_scope(creds: IntercomCredentials):
    """Set `_credentials` for the duration of the `with` block and guarantee
    it is cleared afterwards, success or failure (SOP S3.3)."""
    token = _credentials.set(creds)
    try:
        yield
    finally:
        _credentials.reset(token)


def _normalize_region(raw: str | None) -> str:
    region = (raw or DEFAULT_REGION).strip().lower()
    return region if region in INTERCOM_REGION_HOSTS else DEFAULT_REGION


class CredentialMiddleware:
    """ASGI middleware: only guards `/mcp`. `/health` never touches this
    (PRD-21309 AC2 / TC10 -- the health check must not depend on any
    credential or on Intercom reachability)."""

    def __init__(self, app: ASGIApp, guarded_path: str = "/mcp"):
        self.app = app
        self.guarded_path = guarded_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.guarded_path):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        access_token = request.headers.get(ACCESS_TOKEN_HEADER)
        if not access_token:
            response = JSONResponse(
                not_configured_envelope([ACCESS_TOKEN_HEADER]),
                status_code=401,
            )
            await response(scope, receive, send)
            return

        creds = IntercomCredentials(
            access_token=access_token,
            region=_normalize_region(request.headers.get(REGION_HEADER)),
        )
        with credentials_scope(creds):
            await self.app(scope, receive, send)
