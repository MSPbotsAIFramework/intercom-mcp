"""CredentialMiddleware: missing-header 401 (AC2/TC2) and per-request
isolation of the credential ContextVar (AC7/TC9).

The isolation test is the one that would catch a regression to a
module-level/global variable for credentials -- SOP S3.3's core risk.
"""

import asyncio

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from intercom_mcp.middleware import ACCESS_TOKEN_HEADER, CredentialMiddleware, current_credentials


async def _echo_token(request):
    """Reads the ContextVar twice with an `await` in between, so two
    concurrently-handled requests have a chance to interleave and corrupt
    each other's view if credentials were ever stored somewhere shared."""
    first = current_credentials()
    await asyncio.sleep(0.01)
    second = current_credentials()
    return JSONResponse(
        {
            "first": first.access_token if first else None,
            "second": second.access_token if second else None,
            "region": first.region if first else None,
        }
    )


def _build_app() -> Starlette:
    return Starlette(
        routes=[Route("/mcp", _echo_token, methods=["POST"])],
        middleware=[Middleware(CredentialMiddleware)],
    )


def _post(app: Starlette, headers: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/mcp", json={}, headers=headers or {})

    return asyncio.run(run())


def test_missing_access_token_header_returns_401_with_header_name():
    response = _post(_build_app())
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "not_configured"
    assert ACCESS_TOKEN_HEADER in body["error"]["message"]


def test_present_header_reaches_the_contextvar_unchanged():
    response = _post(_build_app(), headers={ACCESS_TOKEN_HEADER: "tenant-a-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["first"] == body["second"] == "tenant-a-token"


def test_missing_region_header_defaults_to_us():
    """Dev-added coverage (source: dev, not an official AC/TC): the
    deterministic half of AC6/TC8 -- omitting X-Intercom-Region must resolve
    to "us". The "call succeeds against a live US workspace" half of TC8
    still needs a real account and stays manual/blocked in the ledger."""
    response = _post(_build_app(), headers={ACCESS_TOKEN_HEADER: "tenant-a-token"})
    assert response.status_code == 200
    assert response.json()["region"] == "us"


def test_concurrent_requests_do_not_leak_credentials_across_contextvars():
    app = _build_app()
    transport = httpx.ASGITransport(app=app)

    async def call(token: str) -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/mcp", json={}, headers={ACCESS_TOKEN_HEADER: token})

    async def run():
        return await asyncio.gather(call("tenant-a-token"), call("tenant-b-token"))

    response_a, response_b = asyncio.run(run())
    body_a, body_b = response_a.json(), response_b.json()
    assert body_a["first"] == body_a["second"] == "tenant-a-token"
    assert body_b["first"] == body_b["second"] == "tenant-b-token"
