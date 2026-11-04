"""Company tools (PRD-21309 tech design: GET /companies, not the broader search
endpoint -- see 'Decisions made by DEV01' for why). Descriptions are a single
verb-first sentence (AC1)."""

from intercom_mcp.client import IntercomClient
from intercom_mcp.errors import INVALID_ARGUMENT, error_envelope
from intercom_mcp.tools._shared import clamp_limit, execute, list_result


def _shape_company(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "company_id": raw.get("company_id"),
        "name": raw.get("name"),
        "monthly_spend": raw.get("monthly_spend"),
        "user_count": raw.get("user_count"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def register(mcp) -> None:
    @mcp.tool(
        description="Look up companies by name or your own company_id.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_search_companies(
        name: str | None = None,
        company_id: str | None = None,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> str:
        async def _run(client: IntercomClient) -> dict:
            if not name and not company_id:
                return error_envelope(
                    INVALID_ARGUMENT, "Provide at least one of: name, company_id"
                )
            params = {"per_page": clamp_limit(limit)}
            if name:
                params["name"] = name
            if company_id:
                params["company_id"] = company_id
            if starting_after:
                params["starting_after"] = starting_after
            data = await client.request("GET", "/companies", params=params)
            companies = [_shape_company(c) for c in data.get("data", [])]
            next_page = (data.get("pages") or {}).get("next") or {}
            return list_result(
                companies,
                has_more=bool(next_page),
                next_cursor=next_page.get("starting_after") if isinstance(next_page, dict) else None,
            )

        return await execute(_run)

    @mcp.tool(
        description="Get a single company by its Intercom id.",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def intercom_get_company(company_id: str) -> str:
        async def _run(client: IntercomClient) -> dict:
            data = await client.request("GET", "/companies/%s" % company_id)
            return _shape_company(data)

        return await execute(_run)
