# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
