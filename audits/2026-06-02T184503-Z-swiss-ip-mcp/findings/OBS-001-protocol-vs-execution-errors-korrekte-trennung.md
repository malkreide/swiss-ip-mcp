## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-001` |
| **PDF-Reference** | Sec 6.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Jeder Tool-Handler faengt Exceptions ab und liefert {"error": ...} (z.B. server.py:585-586)
- Test deckt Execution-Error-Pfad ab (test_search_trademarks_api_error, test_get_trademark_not_found)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-001) verlangt die Behebung folgender Luecken:

- Fehler werden als normales String-Result {"error":...} zurueckgegeben, NICHT mit MCP isError:true — LLM kann Fehler nicht von Erfolg unterscheiden
- Kein Test fuer Protocol-Level-Error-Pfad (falsches Tool/Args)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OBS-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (OBS-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
