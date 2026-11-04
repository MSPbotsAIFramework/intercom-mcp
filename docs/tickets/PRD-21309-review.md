# PRD-21309 · Code review

## Round 1 · 2026-11-04 · reviewed dev/PRD-21309 @ 92230bd (base main@abc5237)

Verdict: approved

### Scope

Diff `origin/main...92230bd` (26 files, 3352 insertions) — the entire first version of `MSPbotsAIFramework/intercom-mcp`: `src/intercom_mcp/` (app, settings, middleware, client, errors, 5 `tools/*.py` modules), `tests/` (test_tools.py, test_middleware.py), `Dockerfile`, `pyproject.toml`/`uv.lock`, README, `docs/tickets/PRD-21309.md` + `.ac.json`.

### Verification performed (commands run, not just re-read self-test claims)

- `uv sync && uv run pytest -q` → **16 passed**, 0 failed — matches the `[DEV]` stub and the doc's Self-test table exactly.
- `grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .` → no output — confirmed no Chinese anywhere in the repo (SOP §0.4).
- `diff` of README.md:14-84 against `vendor-mcp-development/reference/readme-connector-section.md` → **identical**, and it sits before the Header credential table (SOP §0.5/§14).
- Live smoke (`uv run python -m intercom_mcp` on 127.0.0.1:8080):
  - `GET /health` → 200 `{"status":"ok"}`.
  - `POST /mcp` with `X-Intercom-Access-Token: placeholder` → `initialize` 200, `tools/list` 200 with all 14 `intercom_*` tools, schemas, and annotations (`readOnlyHint`/`destructiveHint`/`idempotentHint`) present.
  - `POST /mcp` with no access-token header → 401 `{"error":{"code":"not_configured","message":"Missing required header(s): X-Intercom-Access-Token","retryable":false}}` (AC2/TC2).
  - `POST /mcp` with a spoofed non-localhost `Host:` header (`intercom-mcp.internal.mspbots.ai`) → 200, not 421 — independently confirms the doc's DNS-rebinding claim (SOP §7) rather than taking it on trust.
- Read every source file in `src/intercom_mcp/` and both test files line by line (not excerpted).

### Findings

No must-fix. Two suggestions:

1. [suggestion] `src/intercom_mcp/tools/_shared.py:37-41` — `execute()` only catches `IntercomApiError`; a malformed (non-JSON) 2xx body from Intercom would raise an uncaught `json.JSONDecodeError` out of a tool function instead of returning the structured error envelope. Low likelihood (Intercom's documented API always returns JSON on 2xx) and FastMCP itself prevents this from crashing the process (a raised exception becomes an `isError:true` tool result, not a server crash), but it is a gap against AC5's "never raises an unhandled exception" wording. Widening the `except` in `execute()` to also catch generic `Exception` and map it to `upstream_error` would close it; not blocking because it only degrades error-shape consistency on an input Intercom's own contract says won't happen.
2. [suggestion] No structured per-call logging (tool name / status / latency) yet — already flagged and justified by the dev in the doc's "Decisions made during implementation" (gateway audit log is the system of record; nothing to debug yet). Agree this is reasonable to defer, but worth adding before meaningful production traffic for debugging upstream failures (SOP §6).

### Other checks (all clean, no finding)

- Credential isolation: `middleware.py`'s `ContextVar` is request-scoped and reset in `finally`; `client.py` builds one `httpx.AsyncClient` per call from the credentials already resolved for that request — no module/global state holding a token. `tests/test_middleware.py::test_concurrent_requests_do_not_leak_credentials_across_contextvars` and the live double-request check both confirm this.
- Error vocabulary: every HTTP status Intercom can return (401/403/404/400/422/429/5xx) maps through `errors.code_for_status` to the fixed vocabulary; 403→`unauthorized` is a deliberate, documented choice (missing OAuth scope should read as actionable-by-tenant, not a generic upstream failure).
- Pagination: `list_result()` gives every list/search tool one shared `items`/`has_more`/`next_cursor` shape and forces `has_more=true` if it has to truncate for the 20,000-char budget (SOP §2.5); `clamp_limit()` can't be driven negative or past 100.
- README Header table, Tools table and the `Authentication headers` section match `middleware.py`'s header names and `tools/__init__.py`'s registered tool set exactly (14 tools, 4 domains, no delete tools — matches the "Decisions made by DEV01" non-goal).
- Dockerfile: multi-stage, non-root `app` user in the production stage, `curl` installed, `EXPOSE 8080`, `HEALTHCHECK` against `/health`, default `MCP_HTTP_PORT`/`MCP_HTTP_HOST` — matches SOP §8 reference sample; not build-verified in this session either (same missing `docker` group permission the dev flagged), carried forward as the same pre-existing local blind spot, not a new gap.
- `docs/tickets/PRD-21309.ac.json` ledger matches the doc's test-case matrix; TC3/TC4/TC5/TC6/TC8 are `blocked` with "needs a real vendor account" reasons, not silently marked pass — acceptable per `mcp-track.md` §3 ("missing vendor test account does not block").
- Handoff's suggested `/api/vendor-register` payload: `credential_fields` keys (`X-Intercom-Access-Token`, `X-Intercom-Region`) match the header names the code actually reads, letter for letter.
- Commit identity on this branch is mixed (`Dev01.MBAgent <dev01.mbagent@mspbots.ai>` on the two design commits made on an earlier host, `mspbots-mbagent-dev[bot] (dev07)` on the two dev commits) — this round's instructions are explicit that commit authorship follows each machine's local git global config and must not be changed by the review leg, so this is left as-is and is not raised as a finding.

Status: frozen @ 92230bd
