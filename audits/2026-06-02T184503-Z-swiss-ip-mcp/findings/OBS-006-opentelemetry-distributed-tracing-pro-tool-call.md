## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-006) verlangt die Behebung folgender Luecken:

- Keine OpenTelemetry-Integration (kein opentelemetry-Dependency, keine TracerProvider/OTLP-Exporter)
- Keine httpx-Auto-Instrumentation, keine per-Tool-Call-Spans

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/OBS-006.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (OBS-006) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
