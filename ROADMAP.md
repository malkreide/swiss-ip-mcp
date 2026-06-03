# Roadmap

This server follows the phased rollout model from the MCP best-practice catalog
(read-only first, then write-capable, then multi-agent — OPS-003). The current
phase is declared in the README; phase transitions are recorded in
[`CHANGELOG.md`](CHANGELOG.md).

## Phase 1 — Read-only  ✅ current

All tools are read-only (`readOnlyHint: true`); nothing is written, modified or
deleted on any system.

- [x] Trademark / patent / patent-publication / SPC search + number lookup
- [x] Cross-domain recent-filings + quota
- [x] Provenance + typed, structured responses
- [x] Audit hardening: SSE/HTTP transport, container hardening, egress
      allow-list, tool-definition pinning, OpenTelemetry, structured logging

## Phase 2 — Write-capable  ⬜ not started

Prerequisites before entering Phase 2 (per catalog): completed audit run, ISDS
(Informationssicherheits- und Datenschutzkonzept), DSG-Verarbeitungsverzeichnis.

- [ ] No write-capable tools are planned at this time. The IGE Swissreg
      Datadelivery API is a read-only data source.

## Phase 3 — Multi-agent / semantic  ⬜ not started

Prerequisites: semantic layer, identity resolution, GL sign-off and
data-protection-officer sign-off.

- [ ] None planned.
