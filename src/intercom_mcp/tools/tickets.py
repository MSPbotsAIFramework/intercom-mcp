"""Ticket tools (PRD-21309 tech design S "Data & API contract").

Some workspaces do not have the Tickets product area enabled; Intercom then
responds with a scope/permission error that `errors.code_for_status` maps to
`unauthorized` (see PRD-21309.md "Risks & dependencies"). Descriptions are a
single verb-first sentence (AC1).
"""

from typing import Literal

from intercom_mcp.client import IntercomClient
from intercom_mcp.tools._shared import clamp_limit, execute, list_result


def _shape_ticket(raw: dict) -> dict:
    ticket_type = raw.get("ticket_type") or {}
    return {
        "id": raw.get("id"),
        "ticket_type": ticket_type.get("name"),
        "ticket_type_id": ticket_type.get("id"),
        "state": raw.get("ticket_state_internal") or raw.get("state"),
        "open": raw.get("open"),
        "admin_assignee_id": raw.get("admin_assignee_id"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def register(mcp) -> None:
    @mcp.tool(
        description="List tickets, optionally filtered by state and/or contact.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_list_tickets(
        state: str | None = None,
        contact_id: str | None = None,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            clauses = []
            if state:
                clauses.append(
                    {"field": "ticket_state_internal", "operator": "=", "value": state}
                )
            if contact_id:
                clauses.append(
                    {"field": "contact_ids", "operator": "=", "value": contact_id}
                )
            if not clauses:
                query = {"field": "open", "operator": "=", "value": "true"}
            elif len(clauses) == 1:
                query = clauses[0]
            else:
                query = {"operator": "AND", "value": clauses}
            body = {
                "query": query,
                "pagination": {"per_page": clamp_limit(limit)},
            }
            if starting_after:
                body["pagination"]["starting_after"] = starting_after
            data = await client.request("POST", "/tickets/search", json=body)
            tickets = [_shape_ticket(t) for t in data.get("tickets", [])]
            next_page = (data.get("pages") or {}).get("next") or {}
            return list_result(
                tickets,
                has_more=bool(next_page),
                next_cursor=next_page.get("starting_after") if isinstance(next_page, dict) else None,
            )

        return await execute(_run)

    @mcp.tool(
        description="Get a single ticket by its Intercom id.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_get_ticket(ticket_id: str) -> str:
        async def _run(client: IntercomClient) -> dict:
            data = await client.request("GET", "/tickets/%s" % ticket_id)
            return _shape_ticket(data)

        return await execute(_run)

    @mcp.tool(
        description="Create a ticket for a contact under a given ticket type.",
        annotations={"destructiveHint": False},
    )
    async def intercom_create_ticket(
        ticket_type_id: str,
        contact_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            attributes = {
                k: v
                for k, v in {"_default_title_": title, "_default_description_": description}.items()
                if v is not None
            }
            body = {
                "ticket_type_id": ticket_type_id,
                "contacts": [{"id": contact_id}],
                "ticket_attributes": attributes,
            }
            data = await client.request("POST", "/tickets", json=body)
            return _shape_ticket(data)

        return await execute(_run)

    @mcp.tool(
        description="Reply to a ticket as an admin, publicly or as an internal note.",
        annotations={"destructiveHint": False},
    )
    async def intercom_reply_ticket(
        ticket_id: str,
        admin_id: str,
        body: str,
        message_type: Literal["comment", "note"] = "comment",
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            payload = {
                "message_type": message_type,
                "type": "admin",
                "admin_id": admin_id,
                "body": body,
            }
            data = await client.request("POST", "/tickets/%s/reply" % ticket_id, json=payload)
            return _shape_ticket(data)

        return await execute(_run)
