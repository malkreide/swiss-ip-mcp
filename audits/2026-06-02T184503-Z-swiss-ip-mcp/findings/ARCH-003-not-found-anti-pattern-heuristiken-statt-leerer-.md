## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Not-Found-Meldungen enthalten actionable Hinweis zum Nummernformat (server.py:657-659, 785-789)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-003) verlangt die Behebung folgender Luecken:

- Negatives 'nicht gefunden'-Framing ohne match_type-Feld
- Keine Fuzzy-Match-/Suggestion-Mechanik bei leeren Suchergebnissen der Search-Tools

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
