"""Conversation tools (PRD-21309 tech design S "Data & API contract").

Tool descriptions are a single verb-first sentence (AC1); enum-like
parameters use `Literal` instead of prose so the constraint is in the schema,
not the description (SOP S2.2/S2.4).
"""

from typing import Literal

from intercom_mcp.client import IntercomClient
from intercom_mcp.tools._shared import clamp_limit, execute, list_result


def _shape_part(raw: dict) -> dict:
    author = raw.get("author") or {}
    return {
        "id": raw.get("id"),
        "part_type": raw.get("part_type"),
        "body": raw.get("body"),
        "author_type": author.get("type"),
        "author_id": author.get("id"),
        "created_at": raw.get("created_at"),
    }


def _shape_conversation(raw: dict, include_parts: bool = False) -> dict:
    source = raw.get("source") or {}
    shaped = {
        "id": raw.get("id"),
        "state": raw.get("state"),
        "open": raw.get("open"),
        "priority": raw.get("priority"),
        "admin_assignee_id": raw.get("admin_assignee_id"),
        "source_body": source.get("body"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }
    if include_parts:
        parts = (raw.get("conversation_parts") or {}).get("conversation_parts", [])
        shaped["conversation_parts"] = [_shape_part(p) for p in parts]
    return shaped


def register(mcp) -> None:
    @mcp.tool(
        description="Search conversations by state and/or contact, newest first.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_search_conversations(
        state: Literal["open", "closed", "snoozed"] | None = None,
        contact_id: str | None = None,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            clauses = []
            if state:
                clauses.append({"field": "state", "operator": "=", "value": state})
            if contact_id:
                clauses.append(
                    {"field": "contact_ids", "operator": "=", "value": contact_id}
                )
            if not clauses:
                query = {"field": "state", "operator": "=", "value": "open"}
            elif len(clauses) == 1:
                query = clauses[0]
            else:
                query = {"operator": "AND", "value": clauses}
            body: dict = {
                "query": query,
                "pagination": {"per_page": clamp_limit(limit)},
            }
            if starting_after:
                body["pagination"]["starting_after"] = starting_after
            data = await client.request("POST", "/conversations/search", json=body)
            conversations = [_shape_conversation(c) for c in data.get("conversations", [])]
            next_page = (data.get("pages") or {}).get("next") or {}
            return list_result(
                conversations,
                has_more=bool(next_page),
                next_cursor=next_page.get("starting_after"),
            )

        return await execute(_run)

    @mcp.tool(
        description="Get a conversation including its full reply thread.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_get_conversation(conversation_id: str) -> str:
        async def _run(client: IntercomClient) -> dict:
            data = await client.request("GET", "/conversations/%s" % conversation_id)
            return _shape_conversation(data, include_parts=True)

        return await execute(_run)

    @mcp.tool(
        description="Reply to a conversation as an admin, publicly or as an internal note.",
        annotations={"destructiveHint": False},
    )
    async def intercom_reply_conversation(
        conversation_id: str,
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
            data = await client.request(
                "POST", "/conversations/%s/reply" % conversation_id, json=payload
            )
            return _shape_conversation(data, include_parts=True)

        return await execute(_run)
