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

- Kurze, klar abgegrenzte Tool-Handler

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-003) verlangt die Behebung folgender Luecken:

- Kein Tool nutzt ctx:Context — API-Calls bis zu 60s ohne ctx.report_progress()
- response_format-Parameter (markdown/json) wird akzeptiert, aber ignoriert — Tools liefern immer json.dumps (z.B. server.py:584), 'markdown' nie erzeugt

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SDK-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
