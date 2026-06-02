## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-001) verlangt die Behebung folgender Luecken:

- Keine Lifespan-Funktion (@asynccontextmanager) definiert; FastMCP-Konstruktor erhaelt kein lifespan= (server.py:330-339)
- _call_api erzeugt pro Tool-Call eine neue httpx.AsyncClient()-Instanz (server.py:97) — kein Connection-Pooling, neue TCP/TLS-Handshakes je Request
- Verletzt explizit das Pass-Kriterium 'Keine httpx.AsyncClient() pro Tool-Call'

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SDK-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
