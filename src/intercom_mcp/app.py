"""ASGI app: FastMCP server (stateless Streamable HTTP) + a local /health probe.

PRD-21309 contract notes:
- `/health` is registered via `FastMCP.custom_route`, so it lives on the same
  Starlette app `http_app()` returns -- no `Mount()` is involved, so there is
  no "child app lifespan never runs" trap (SOP S7) to begin with.
- `stateless_http=True`: no session affinity, no per-instance state.
- DNS-rebinding Host/Origin checks: the installed `mcp` SDK
  (`mcp.server.transport_security.TransportSecurityMiddleware`) disables this
  check by default when no `TransportSecuritySettings` are supplied, which is
  what `create_streamable_http_app` does here. That default is correct for
  this service (SOP S7): it sits behind the MSPbots gateway, not exposed
  directly, so a Host-header check written for a browser-facing + ancestor
  service would only break legitimate gateway traffic.
"""

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from intercom_mcp.middleware import CredentialMiddleware
from intercom_mcp.tools import register_all


def _build_mcp_server():
    from fastmcp import FastMCP

    mcp = FastMCP(
        name="intercom-mcp",
        instructions=(
            "Tools for Intercom customer-support data: contacts, conversations, "
            "companies, and tickets. Use intercom_search_contacts or "
            "intercom_get_contact to look up a customer, intercom_search_conversations "
            "/ intercom_get_conversation to read support threads, and "
            "intercom_reply_conversation / intercom_reply_ticket to respond -- pass "
            "message_type='comment' for a customer-visible reply or 'note' for an "
            "internal-only note. intercom_list_admins resolves the admin_id values "
            "reply and ticket tools accept. All tools need an Intercom Personal "
            "Access Token in the X-Intercom-Access-Token header; X-Intercom-Region "
            "defaults to 'us' if omitted."
        ),
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        # Deliberately independent of Intercom: never calls client.py.
        return JSONResponse({"status": "ok"})

    register_all(mcp)
    return mcp


def create_app() -> Starlette:
    mcp = _build_mcp_server()
    return mcp.http_app(
        path="/mcp",
        transport="streamable-http",
        stateless_http=True,
        middleware=[Middleware(CredentialMiddleware)],
    )


app = create_app()
