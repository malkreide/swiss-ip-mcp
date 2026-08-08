# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Hinzugefuegt

- **Die Adressliste ist ohne Zugangsdaten geprueft — Ergebnis: Nullbefund.**
  Jede Adresse, der Keycloak-Realm und der `client_id`, die dieser Server
  baut, sind die, die die Quelle fuehrt.

  Das ist eine gute Nachricht und steht genau deshalb hier: Ein Nullbefund,
  den niemand aufgezeichnet hat, ist beim naechsten Durchgang keiner mehr.

  Drei unabhaengige Belege, weil einer nicht getragen haette:

  1. **Der IDP unterscheidet drei Faelle.** `realms/egov` mit falschen
     Zugangsdaten liefert `invalid_grant` («Invalid user credentials»), ein
     erfundener Realm 404 «Realm does not exist», ein erfundener `client_id`
     `invalid_client`. Realm und Client existieren also, und es fehlen nur
     die Zugangsdaten.

  2. **Der Realm nennt seinen Token-Endpunkt selbst.**
     `.well-known/openid-configuration` liefert ihn — identisch mit der
     gebauten URL.

  3. **Die offizielle API-Doku deklariert beide Adressen woertlich**,
     einschliesslich des `client_id` als «constant string» und
     `grant_type=password`.

- **Warum es den dritten Beleg braucht.** Die Swissreg-API selbst
  unterscheidet **nicht**: Ein POST ohne Token gibt HTTP 403, mit erfundenem
  Token HTTP 401 — und ein frei erfundener Pfad unter `/public/api/` gibt
  jeweils dasselbe. Ein Statuscode belegt dort nichts.

  Dieselbe Lage gab es bei `epl.bag.admin.ch` im selben Portfolio, und dort
  wurde aus einem 401 faelschlich «die Route existiert» geschlossen. Der
  Recorder prueft deshalb bei jedem Lauf mit, dass die Kontrollen noch
  unterscheiden — und bricht ab, wenn die API anfaengt zu unterscheiden.
  Auch das waere eine gute Nachricht und trotzdem ein Anlass, neu zu messen.

- **`scripts/record_fixtures.py`, `tests/fixtures/` und `PROVENANCE.md`.** Die
  Antwort-Payloads sind darin ausdruecklich als **NICHT aufgezeichnet**
  gefuehrt, mit dem gemessenen Statuscode als Grund — statt ihnen ein Datum
  anzuschreiben, das sie nie hatten.

  Ausdruecklich offen bleibt damit die **Form** der Antworten: ob die
  XML-Felder so heissen, wie der Parser sie liest. Genau dort lagen in diesem
  Portfolio die teuersten Fehler.

- **`tests/test_adressen.py`** — 8 Tests, die **in** der CI laufen.
  Gegengeprueft mit zwei Rueckmutationen (`CLIENT_ID` und `API_ENDPOINT` auf
  andere Werte): beide machen die Suite rot.


## [1.1.6] - 2026-08-02

### Fixed

- **`structlog` carried no upper bound, and the index already serves a major past
  the floor.** The declared range was `structlog>=24.1.0`; PyPI has been serving
  `26.1.0`. The artefact does not change — the resolver's answer to the next
  fresh install does, and that is exactly how `swiss-energy-mcp` 0.3.3 became
  uninstallable when `mcp` 2.0.0 removed the module it imported.

  Now `structlog>=24.1.0,<27`. The bound is measured rather than guessed: this package
  installs and imports against `structlog 26.1.0` today, so the cap admits what
  demonstrably works and stops only the next, unknown major.

- **`starlette` carried no upper bound, and the index already serves a major past
  the floor.** The declared range was `starlette>=0.40.0`; PyPI has been serving
  `1.3.1`. The artefact does not change — the resolver's answer to the next
  fresh install does, and that is exactly how `swiss-energy-mcp` 0.3.3 became
  uninstallable when `mcp` 2.0.0 removed the module it imported.

  Now `starlette>=0.40.0,<2`. The bound is measured rather than guessed: this package
  installs and imports against `starlette 1.3.1` today, so the cap admits what
  demonstrably works and stops only the next, unknown major.

A dependency range only reaches users through a new release, hence the
version bump. No code changed.

## [1.1.5] - 2026-07-31

### Hinzugefuegt

- **Der Server nennt jetzt seinen Namen.** Bisher ging gegenueber jedem
  Upstream der httpx-Default hinaus: der Betreiber der Datenquelle sah
  eine Bibliothek, nicht uns, und hatte keinen Weg, uns bei Fehlverhalten
  zu erreichen. Neu traegt den HTTP-Client
  `swiss-ip-mcp/<version> (+github.com/malkreide/swiss-ip-mcp)`.

  Die Version stammt aus `importlib.metadata` und kann nicht getrennt vom
  Paket driften.

### Fixed

- **Declared `mcp` explicitly and capped it at `<2`.** This server imports
  `mcp.server.fastmcp`, but never declared `mcp` — it arrived transitively via
  `fastmcp`. `mcp` 2.0.0, published 2026-07-28, removed that module, and the
  only reason installs still work today is an upper bound inside `fastmcp-slim`,
  a package this project never names. The dependency that is actually imported
  is now declared and bounded here rather than left to someone else's resolver.

### Added
- **`SECURITY.md` / `SECURITY.de.md`**: a bilingual security policy documenting
  the security posture, hardening summary, vulnerability reporting, and the
  portfolio-level accepted risks (SEC-014 / SEC-015). Linked from both READMEs.

### Changed
- **Documentation alignment with the Swiss Public Data MCP Portfolio**: READMEs
  now lead with the portfolio banner, an emoji title, and the standard badge row;
  the portfolio links in `CONTRIBUTING` point to the portfolio landing repo.
- **License copyright holder** corrected to `Hayal Oezkan` (LICENSE + READMEs).

## [1.1.1] - 2026-06-03

Closes the last three (non-blocking) audit partials. Confirming re-audit
`2026-06-03T062701-Z-swiss-ip-mcp`: **44 pass / 0 partial / 0 fail**.

### Added
- **Progress reporting** (SDK-003): tools accept an injected `ctx: Context` and
  report progress around the (up to 60s) Swissreg API call via
  `ctx.report_progress`. `ctx` is excluded from the tool input schema, so the
  tool manifest is unchanged.
- **Secret-scanning CI** (ARCH-005): a gitleaks workflow scans PRs and `main`
  for accidentally committed secrets.
- **Phase declaration + roadmap** (OPS-003): the README declares Phase 1
  (read-only) and a new `ROADMAP.md` documents the phased rollout and the
  prerequisites for future phases.

### Changed
- **Credentials are now held as `pydantic.SecretStr`** (ARCH-005) via a typed
  `_Credentials` model, so they cannot leak through `repr()` / logs.

## [1.1.0] - 2026-06-03

Audit-hardening release. Closes every blocking finding from the mcp-audit-skill
audit (re-audit run `2026-06-03T055425-Z-swiss-ip-mcp`: 41 pass / 3 partial /
0 fail — production-ready).

### Added
- **Egress allow-list** (SEC-021): an immutable `ALLOWED_EGRESS_HOSTS` frozenset
  is enforced by `_assert_host_allowed()` before every outgoing request —
  defense-in-depth against egress to any host other than the fixed IGE endpoints.
- **Tool-definition pinning** (SEC-022): `tool_manifest.json` pins a SHA-256
  fingerprint of every tool definition; a test fails if the tool surface drifts,
  forcing an intentional regeneration via `scripts/update_tool_manifest.py`.
- **Live-test workflow** (OPS-001): `.github/workflows/live.yml` runs the
  `@pytest.mark.live` integration tests on a weekly schedule / manual dispatch
  (separate from credential-free CI). New respx-based tests exercise the real
  HTTP path (token + API + egress guard + parser), not just a mocked `_call_api`.
- **Container & cloud deployment** (SEC-007 / SCALE-002 / SCALE-003 / SCALE-004 /
  SCALE-006): a hardened multi-stage `Dockerfile` (non-root UID 10001,
  `HEALTHCHECK`), `docker-compose.yml` with resource limits (memory/CPU/PIDs/FDs)
  and read-only rootfs, Kubernetes manifests with a full `securityContext`
  (runAsNonRoot, dropped capabilities, seccomp, read-only rootfs) and resource
  requests/limits, plus an HAProxy config that pins `Mcp-Session-Id` to a backend
  for stateful mode. A `GET /health` endpoint backs container/LB probes, and
  `MCP_STATELESS_HTTP=1` enables affinity-free horizontal scaling. See
  `docs/deployment.md`.
- **MCP Resources & Prompts** (ARCH-008): the server now exposes all three MCP
  primitives. Resources `swissip://about` and `swissip://domains` provide
  read-only metadata; prompts `trademark_availability`, `competitor_ip_report`
  and `recent_ip_filings_report` offer curated workflow templates.

### Changed
- **Error semantics** (OBS-001): tool execution errors (API failures, timeouts,
  missing credentials) are now raised, so clients receive MCP `isError: true`
  with a masked message instead of a normal result containing an `error` key. A
  number lookup with no match is no longer reported as an error — it returns a
  normal result with `match_type: "none"` and a `message` field.
- **Repo hygiene** (ARCH-012): a `.github/dependabot.yml` keeps the `mcp` /
  `fastmcp` SDK and GitHub Actions current via monthly PRs; READMEs gained an
  "MCP Protocol Version" section documenting the negotiated version and the SDK
  update policy.

### Fixed
- Tool-manifest fingerprints (SEC-022) are now stable across Python versions:
  the description is normalised with `inspect.cleandoc` before hashing, so
  Python 3.13's compile-time docstring dedenting no longer breaks
  `TestToolManifest` on the 3.13 CI job. Manifest regenerated.
- Consolidated the duplicate `[1.0.0]` CHANGELOG entries (which carried two
  conflicting dates) into a single coherent release section.
- **Structured logging** (OBS-003): logs are now emitted as JSON on stderr via
  `structlog` (stdout stays clean for the stdio protocol). Each tool call binds
  a `tool` name and `correlation_id`; four severity levels are used. Level is
  configurable via `LOG_LEVEL` (default `INFO`).
- **Tool ergonomics** (ARCH-002 / ARCH-003): every tool description now carries a
  `<use_case>` tag (plus `<important_notes>` where relevant). Search/list
  responses include a `match_type` field (`exact` / `none`) and, on empty
  results, an actionable `suggestion` instead of a bare empty list. Number
  lookups are documented as exact-only.
- **Typed responses + provenance** (SDK-002 / CH-004): tools now return typed
  Pydantic models (`SearchEnvelope` / `QuotaEnvelope`) instead of JSON strings,
  so FastMCP emits a JSON schema (`outputSchema`) and `structuredContent`. Every
  response carries a typed `source` provenance block (provider, source URL,
  license); the search/list envelope is
  `{ source, total, count, match_type, results, next_page_token, … }`. README
  documents the data license explicitly.
- **Optional OpenTelemetry tracing** (`MCP_OTEL_ENABLED=1`, install
  `swiss-ip-mcp[otel]`): one span per tool call (`mcp.tool.name`,
  `mcp.tool.result.is_error`) plus httpx auto-instrumented child spans for
  backend calls. Off by default and no-op without a provider; spans carry no
  query args, credentials or response bodies.
- **Streamable HTTP / SSE transport actually implemented** (was previously only
  documented). `main()` now selects the transport from `MCP_TRANSPORT`
  (`stdio` default, `sse`, `streamable-http`) and serves HTTP under uvicorn.
- Configurable network binding via `MCP_HOST` (default `127.0.0.1`) and
  `PORT` / `MCP_PORT`; a warning is logged when binding to `0.0.0.0` outside a
  detected container.
- CORS for HTTP transports: `Mcp-Session-Id` is exposed/accepted, origins are
  restricted via `MCP_ALLOWED_ORIGINS` (no wildcard in production).
- Optional DNS-rebinding protection via `MCP_ALLOWED_HOSTS` /
  `MCP_ALLOWED_ORIGINS`.
- Pooled `httpx.AsyncClient` owned by a server lifespan — connections are now
  reused across tool calls instead of a new client per request.
- `.env.example` with placeholders for credentials and transport configuration.

### Changed
- **Response field rename:** the search/list result array is now `results`
  (was `items`), and responses gained a top-level `source` block. Consumers
  reading `items` must switch to `results`.
- `_call_api` uses the shared pooled HTTP client instead of opening a new
  `httpx.AsyncClient` on every call.
- README / README.de transport sections updated to match the implementation,
  including a security note for public deployments.
- **Removed the `response_format` / Markdown option** in favour of fully typed
  returns (SDK-002): tools always return structured data now, which MCP clients
  receive as both JSON text and `structuredContent`.
- `swiss_ip_get_quota` now declares `openWorldHint: true` (it reaches the
  external IGE API).

### Fixed
- Error messages no longer leak internals (exception reprs, raw upstream
  response bodies) to the client; full detail is logged server-side only.

### Notes
- Remediates audit findings SCALE-001 (transport drift) and SDK-001 (client
  lifecycle); hardens SDK-004 (CORS), SEC-016 (host binding) and SEC-005
  (DNS-rebinding). Quick-wins address OBS-002 (error masking) and ARCH-009
  (`openWorldHint`); OBS-006 adds optional
  distributed tracing. The HTTP endpoint remains unauthenticated by design and
  serves only public IP-register data.

## [1.0.0] - 2026-03-29

Initial release.

### Added
- **Trademarks**: `swiss_ip_search_trademarks`, `swiss_ip_get_trademark`,
  `swiss_ip_search_trademarks_by_owner`, `swiss_ip_search_trademarks_by_class`
- **Patents**: `swiss_ip_search_patents`, `swiss_ip_get_patent`,
  `swiss_ip_search_patents_by_applicant`, `swiss_ip_search_patent_publications`
- **SPC/ESZ**: `swiss_ip_search_spc`
- **Cross-domain**: `swiss_ip_search_recent_filings`, `swiss_ip_get_quota`
- Dual transport: stdio (Claude Desktop) and SSE (Render.com / cloud)
- OAuth2 token management with auto-refresh via IGE IDP
- XML request builder and response parser for the Swissreg Datadelivery API
- Comprehensive test suite (unit + integration smoke tests)
- GitHub Actions CI (Python 3.11 / 3.12 / 3.13)
- Bilingual README (Deutsch / English)
- Successor to `patent-mcp`; covers all Swissreg API domains

### Notes
- Requires free IGE API credentials (sign usage terms at ige.ch)
- Design search not yet available (no DesignSearch action in the API)
