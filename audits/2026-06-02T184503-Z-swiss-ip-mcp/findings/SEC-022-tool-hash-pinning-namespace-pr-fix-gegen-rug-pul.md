## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Alle Tools tragen konsistentes Namespace-Praefix mit Server-Identitaet (swiss_ip_*, z.B. server.py:552)
- CHANGELOG listet Tool-Definitionen explizit

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SEC-022) verlangt die Behebung folgender Luecken:

- Kein Tool-Definition-Hash-Snapshot im Repo (kein Rug-Pull-Schutz)
- Praefix nutzt einfaches _ statt der empfohlenen <server>__<tool>-Doppelunterstrich-Konvention

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SEC-022.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SEC-022) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
