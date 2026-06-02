## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server nutzt das Tools-Primitiv sauber und konsistent

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-008) verlangt die Behebung folgender Luecken:

- Nur Tools verwendet — keine Resources oder Prompts
- Read-only-Lookups (z.B. get_trademark/get_patent) sind Resource-Migrations-Kandidaten; keine dokumentierte Begruendung fuer Tools-only

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-008.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (ARCH-008) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
