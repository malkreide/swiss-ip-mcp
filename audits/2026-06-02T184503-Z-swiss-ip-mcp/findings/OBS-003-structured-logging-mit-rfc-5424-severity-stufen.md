## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Logging vorhanden via stdlib logging (server.py:30-31)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-003) verlangt die Behebung folgender Luecken:

- Kein strukturierter Logger (structlog/loguru) — kein JSON/logfmt-Output
- Nur info-Level aktiv genutzt (1 Aufruf), keine 4 Severity-Stufen
- Kein per-Tool-Call gebundener Kontext (tool name, session_id, correlation_id)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/OBS-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OBS-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
