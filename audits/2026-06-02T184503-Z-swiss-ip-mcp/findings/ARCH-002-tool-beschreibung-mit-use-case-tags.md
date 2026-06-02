## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-002` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Detaillierte Docstrings > 100 Zeichen mit Args/Returns und Beispielen (z.B. server.py:562-575)
- Differenzierung aehnlicher Tools explizit (search vs by_owner vs by_class)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-002) verlangt die Behebung folgender Luecken:

- Keine strukturierten <use_case>/<important_notes>-XML-Tags in den Tool-Beschreibungen (nur Prosa)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
