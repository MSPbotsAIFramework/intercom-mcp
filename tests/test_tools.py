"""tools/list snapshot (AC1/TC1), error-code mapping and 429 retry (AC5/TC7),
and the health endpoint (AC2/TC10)."""

import asyncio
import re

import httpx
import pytest

from intercom_mcp.app import _build_mcp_server, create_app
from intercom_mcp.client import IntercomClient
from intercom_mcp.errors import (
    INVALID_ARGUMENT,
    NOT_FOUND,
    RATE_LIMITED,
    UNAUTHORIZED,
    UPSTREAM_ERROR,
    IntercomApiError,
    code_for_status,
)
from intercom_mcp.middleware import IntercomCredentials

EXPECTED_TOOL_COUNT = 14
SENTENCE_RE = re.compile(r"^[A-Z][^.\n]*\.$")


async def _tools_list():
    mcp = _build_mcp_server()
    return await mcp.get_tools()


def test_tools_list_snapshot():
    tools = asyncio.run(_tools_list())
    assert len(tools) == EXPECTED_TOOL_COUNT
    for name, tool in tools.items():
        assert name.startswith("intercom_"), name
        description = tool.description.strip()
        assert SENTENCE_RE.match(description), "not a single verb-first sentence: %r" % description
        assert len(description) <= 500


@pytest.mark.parametrize(
    "status_code,expected_code",
    [
        (401, UNAUTHORIZED),
        (404, NOT_FOUND),
        (400, INVALID_ARGUMENT),
        (422, INVALID_ARGUMENT),
        (429, RATE_LIMITED),
        (500, UPSTREAM_ERROR),
        (503, UPSTREAM_ERROR),
    ],
)
def test_status_to_error_code_mapping(status_code, expected_code):
    assert code_for_status(status_code) == expected_code


def test_429_is_retried_with_backoff_before_surfacing():
    attempts = []

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"errors": [{"message": "slow down"}]})
        return httpx.Response(200, json={"ok": True})

    async def run():
        creds = IntercomCredentials(access_token="placeholder-token", region="us")
        async with IntercomClient(creds, transport=httpx.MockTransport(handler)) as client:
            return await client.request("GET", "/admins")

    result = asyncio.run(run())
    assert result == {"ok": True}
    assert len(attempts) == 3  # two 429s, then success -- proves the retry path ran


def test_429_surfaces_as_rate_limited_after_exhausting_retries():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"errors": [{"message": "slow down"}]})

    async def run():
        creds = IntercomCredentials(access_token="placeholder-token", region="us")
        async with IntercomClient(creds, transport=httpx.MockTransport(handler)) as client:
            await client.request("GET", "/admins")

    with pytest.raises(IntercomApiError) as exc_info:
        asyncio.run(run())
    assert code_for_status(exc_info.value.status_code) == RATE_LIMITED


def test_health_endpoint_ok_without_any_credentials():
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Dev-added coverage (source: dev, not an official AC/TC) -- the deterministic
# half of AC6/TC8 that doesn't need a real Intercom workspace: a "us"-region
# credential resolves to the US API host. The "the call actually succeeds
# against a live US workspace" half of TC8 still needs a real account and
# stays manual/blocked in the ledger. Header-absent -> region "us" itself is
# covered in tests/test_middleware.py (middleware's job, not the client's).
def test_us_region_credentials_resolve_to_the_us_host():
    creds = IntercomCredentials(access_token="placeholder-token", region="us")
    client = IntercomClient(creds)
    assert str(client._http.base_url) == "https://api.intercom.io"
