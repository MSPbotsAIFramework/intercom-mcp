"""Helpers reused by every `tools/<resource>.py` module.

Centralizing the credential check / client lifecycle / error mapping here
means an individual tool function only has to describe its one Intercom call
and how to shape the result -- not repeat the not_configured/try/except
boilerplate that error handling would otherwise require in every tool.
"""

from collections.abc import Awaitable, Callable

from intercom_mcp.client import IntercomClient
from intercom_mcp.errors import (
    IntercomApiError,
    dumps,
    envelope_for_api_error,
    not_configured_envelope,
)
from intercom_mcp.middleware import ACCESS_TOKEN_HEADER, current_credentials

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
MAX_RESPONSE_CHARS = 20_000


async def execute(build_result: Callable[[IntercomClient], Awaitable[dict]]) -> str:
    """Resolve the current request's credentials, run `build_result` with a
    fresh `IntercomClient`, and serialize the outcome -- success or mapped
    error -- as the compact JSON string every tool must return (PRD-21309
    AC2, AC5)."""
    creds = current_credentials()
    if creds is None:
        # Reachable only if a tool is invoked without going through the ASGI
        # middleware (e.g. a unit test calling it directly); in production
        # CredentialMiddleware already rejects the request with 401 before
        # any tool runs.
        return dumps(not_configured_envelope([ACCESS_TOKEN_HEADER]))
    try:
        async with IntercomClient(creds) as client:
            result = await build_result(client)
    except IntercomApiError as exc:
        return dumps(envelope_for_api_error(exc))
    return dumps(result)


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def list_result(items: list[dict], has_more: bool, next_cursor: str | None = None) -> dict:
    """Shared shape for every list/search tool (PRD-21309 tech design,
    'Reuse & cleanup': one pagination convention for the whole tool set).
    Truncates to the token-economy budget (SOP S2.5) if the caller handed us
    more items than fit, forcing `has_more=True` in that case."""
    result: dict = {"items": items, "has_more": has_more}
    if next_cursor:
        result["next_cursor"] = next_cursor
    while len(dumps(result)) > MAX_RESPONSE_CHARS and result["items"]:
        result["items"] = result["items"][:-1]
        result["has_more"] = True
    return result
