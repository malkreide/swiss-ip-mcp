## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- _handle_error liefert benutzerfreundliche Meldungen fuer 401/403/429/Timeout (server.py:291-315)
- Keine traceback.format_exc()-Ausgabe an den Client

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-002) verlangt die Behebung folgender Luecken:

- Generischer Zweig leakt Exception-Typ und -Message an den Client: f'Unerwarteter Fehler ({type(e).__name__}): {e}' (server.py:315)
- API-Fehler leakt rohen Upstream-Body an LLM: e.response.text[:500] (server.py:312)
- mask_error_details=True nicht in FastMCP-Init gesetzt (server.py:330)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OBS-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OBS-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
