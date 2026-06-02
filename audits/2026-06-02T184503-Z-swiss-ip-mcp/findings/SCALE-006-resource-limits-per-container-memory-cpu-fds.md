## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Per-Request-Timeout REQUEST_TIMEOUT=60.0 gesetzt (server.py:49) — eine Resource-Control

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-006) verlangt die Behebung folgender Luecken:

- Keine Memory-/CPU-/FD-Limits konfiguriert (keine Container-Resource-Config im Repo)
- Kein dokumentiertes OOM-/Restart-Verhalten

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SCALE-006.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SCALE-006) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
