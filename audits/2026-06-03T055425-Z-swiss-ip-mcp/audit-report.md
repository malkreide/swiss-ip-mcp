# MCP-Server Audit-Report — `swiss-ip-mcp`

**Audit-Datum:** 2026-06-03
**Skill-Version:** 1.0.0
**Catalog-Version:** 2026-04

---

## 1. Executive Summary

Server `swiss-ip-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 41 bestanden, 3 Findings dokumentiert (1 critical, 1 high, 1 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-ip-mcp` |
| Audit-Datum | 2026-06-03 |
| Skill-Version | 1.0.0 |
| Catalog-Version | 2026-04 |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'Render']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 10 | 0 | 1 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 2 | 0 | 1 | 0 | 0 |
| SCALE | 5 | 0 | 0 | 0 | 0 |
| SDK | 3 | 0 | 1 | 0 | 0 |
| SEC | 15 | 0 | 0 | 0 | 0 |
| **Total** | **41** | **0** | **3** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| OPS-003 | OPS | high | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 3 Findings

---

## 5. Detail-Findings

### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Secrets via os.getenv, keine hardcoded Secrets (server.py:129-130)
- .gitignore vorhanden inkl. .env/.env.* (PR #2)
- .env.example mit Platzhaltern vorhanden (PR #3)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-005) verlangt die Behebung folgender Luecken:

- Secrets weiterhin als plain str, nicht pydantic SecretStr (low)
- Kein Gitleaks/Trufflehog-Secret-Scanning in CI (low)

### Risk Description

Siehe Severity `critical`. Details und Remediation im Check-Katalog
`checks/ARCH-005.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-005) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OPS-003` |
| **PDF-Reference** | Anhang C4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server konsistent Phase 1 (read-only, alle Tools readOnlyHint=true)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OPS-003) verlangt die Behebung folgender Luecken:

- Keine explizite Phasen-Deklaration (Phase 1/2/3) im README
- Kein Roadmap-File mit phasenspezifischen Tasks

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OPS-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OPS-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Strukturiertes Logging via structlog (OBS-003) statt print

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-003) verlangt die Behebung folgender Luecken:

- Kein ctx:Context / ctx.report_progress fuer potenziell lange API-Calls (bis 60s) — Context-Injection nicht umgesetzt

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SDK-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **OPS-003** (high, partial)
3. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `2026-04` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-06-03` |


_Generated by tools/build_report.py — do not edit by hand._
