"""Contact tools (PRD-21309 tech design S "Data & API contract").

Tool descriptions are a single verb-first sentence (PRD-21309 AC1): parameter
names carry the rest of the self-description (SOP S2.2 -- don't repeat type
or restate the obvious in prose).
"""

from intercom_mcp.client import IntercomClient
from intercom_mcp.errors import INVALID_ARGUMENT, error_envelope
from intercom_mcp.tools._shared import clamp_limit, execute, list_result


def _shape_contact(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "external_id": raw.get("external_id"),
        "email": raw.get("email"),
        "name": raw.get("name"),
        "phone": raw.get("phone"),
        "role": raw.get("role"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def register(mcp) -> None:
    @mcp.tool(
        description="Search contacts by email or name, newest first.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_search_contacts(
        email: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            field, value = ("email", email) if email else ("name", name)
            if not value:
                return error_envelope(
                    INVALID_ARGUMENT, "Provide at least one of: email, name"
                )
            query: dict = {
                "query": {"field": field, "operator": "=", "value": value},
                "pagination": {"per_page": clamp_limit(limit)},
            }
            if starting_after:
                query["pagination"]["starting_after"] = starting_after
            data = await client.request("POST", "/contacts/search", json=query)
            contacts = [_shape_contact(c) for c in data.get("data", [])]
            next_page = (data.get("pages") or {}).get("next") or {}
            return list_result(
                contacts,
                has_more=bool(next_page),
                next_cursor=next_page.get("starting_after"),
            )

        return await execute(_run)

    @mcp.tool(
        description="Get a single contact by its Intercom id.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_get_contact(contact_id: str) -> str:
        async def _run(client: IntercomClient) -> dict:
            data = await client.request("GET", "/contacts/%s" % contact_id)
            return _shape_contact(data)

        return await execute(_run)

    @mcp.tool(
        description="Create a contact from an email or an external_id.",
        annotations={"destructiveHint": False},
    )
    async def intercom_create_contact(
        email: str | None = None,
        external_id: str | None = None,
        name: str | None = None,
        phone: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            if not email and not external_id:
                return error_envelope(
                    INVALID_ARGUMENT, "Provide at least one of: email, external_id"
                )
            body = {
                k: v
                for k, v in {
                    "email": email,
                    "external_id": external_id,
                    "name": name,
                    "phone": phone,
                }.items()
                if v is not None
            }
            data = await client.request("POST", "/contacts", json=body)
            return _shape_contact(data)

        return await execute(_run)

    @mcp.tool(
        description="Update the given fields on an existing contact.",
        annotations={"destructiveHint": False, "idempotentHint": True},
    )
    async def intercom_update_contact(
        contact_id: str,
        email: str | None = None,
        name: str | None = None,
        phone: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            body = {
                k: v
                for k, v in {"email": email, "name": name, "phone": phone}.items()
                if v is not None
            }
            if not body:
                return error_envelope(
                    INVALID_ARGUMENT, "Provide at least one field to update"
                )
            data = await client.request("PUT", "/contacts/%s" % contact_id, json=body)
            return _shape_contact(data)

        return await execute(_run)
