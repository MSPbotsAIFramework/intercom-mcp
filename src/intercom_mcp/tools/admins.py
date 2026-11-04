"""Admin tools: read-only, used only to resolve admin_id for reply tools
(PRD-21309 'Decisions made by DEV01' -- no admin/team management in v1)."""

from intercom_mcp.client import IntercomClient
from intercom_mcp.tools._shared import execute, list_result


def _shape_admin(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "email": raw.get("email"),
    }


def register(mcp) -> None:
    @mcp.tool(
        description="List the workspace's admins.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_list_admins() -> str:
        async def _run(client: IntercomClient) -> dict:
            data = await client.request("GET", "/admins")
            admins = [_shape_admin(a) for a in data.get("admins", [])]
            return list_result(admins, has_more=False)

        return await execute(_run)
