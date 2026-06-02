# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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

### Changed
- `_call_api` uses the shared pooled HTTP client instead of opening a new
  `httpx.AsyncClient` on every call.
- README / README.de transport sections updated to match the implementation,
  including a security note for public deployments.

### Notes
- Remediates audit findings SCALE-001 (transport drift) and SDK-001 (client
  lifecycle); hardens SDK-004 (CORS), SEC-016 (host binding) and SEC-005
  (DNS-rebinding). The HTTP endpoint remains unauthenticated by design and
  serves only public IP-register data.

## [1.0.0] - 2026-03-29
v1.0.0 — Initial Release

## [1.0.0] – 2026-03-08

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
