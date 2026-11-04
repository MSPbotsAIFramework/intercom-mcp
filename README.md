# intercom-mcp

Intercom MCP server for the MSPbots Agent platform. Gives an agent read and
write access to a tenant's Intercom workspace -- contacts, conversations,
companies, and tickets -- over the MCP Streamable HTTP transport, with
per-tenant credentials supplied by the MSPbots gateway on every request.

Transport: MCP Streamable HTTP (`POST /mcp`), stateless (`stateless_http=True`).
Stack: Python 3.12, FastMCP, httpx.
License: Apache-2.0.

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

Every request to `/mcp` must carry these headers. The gateway supplies them
per tenant; they are never read from an environment variable or a config file.

| Header | Required | Meaning | Where to get it |
|---|---|---|---|
| `X-Intercom-Access-Token` | Yes | Intercom Personal Access Token, sent as `Authorization: Bearer <token>` to the Intercom API | Intercom Developer Hub → your app → Authentication → Personal Access Tokens ([developers.intercom.com](https://developers.intercom.com/docs/build-an-integration/learn-more/authentication)) |
| `X-Intercom-Region` | No (default `us`) | Which Intercom API host to call: `us`, `eu`, or `au` | Intercom workspace settings show the region; omit this header for a standard US-region workspace |

Missing `X-Intercom-Access-Token` returns HTTP 401 with a structured error
body naming the missing header -- the request never reaches Intercom's API.

`Intercom-Version` (the Intercom API version pinned by this connector, currently
`2.11`) is set internally and is not a header the agent or gateway needs to send.

## Tools

14 tools across 4 resource domains. Full list and parameters: call `tools/list`
on the running server, or see `src/intercom_mcp/tools/`.

| Domain | Tools |
|---|---|
| Contacts | `intercom_search_contacts`, `intercom_get_contact`, `intercom_create_contact`, `intercom_update_contact` |
| Conversations | `intercom_search_conversations`, `intercom_get_conversation`, `intercom_reply_conversation` |
| Companies | `intercom_search_companies`, `intercom_get_company` |
| Tickets | `intercom_list_tickets`, `intercom_get_ticket`, `intercom_create_ticket`, `intercom_reply_ticket` |
| Admins (read-only, resolves `admin_id`) | `intercom_list_admins` |

There are no delete tools in this version, and no Articles / Teams / Admin
management tools -- see `docs/tickets/PRD-21309.md` ("Non-goals", "Decisions
made by DEV01") for why.

## Errors

Every tool returns a JSON string. On failure:

```json
{"error": {"code": "unauthorized", "message": "...", "retryable": false}}
```

`code` is one of: `not_configured`, `unauthorized`, `not_found`,
`invalid_argument`, `rate_limited`, `upstream_error`. `rate_limited` and
`upstream_error` are retried internally with backoff before being surfaced;
`retryable` tells the caller whether retrying again would make sense.

## Local development

```bash
uv sync
uv run pytest
uv run python -m intercom_mcp   # serves on 0.0.0.0:8080
```

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H 'X-Intercom-Access-Token: <your Intercom Personal Access Token>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Connector wiki

Published after the first INT deploy (review leg, `mcp-track.md` §4.5):
`https://docs.mspbots.ai/connectors/intercom/` (link filled in once live).
