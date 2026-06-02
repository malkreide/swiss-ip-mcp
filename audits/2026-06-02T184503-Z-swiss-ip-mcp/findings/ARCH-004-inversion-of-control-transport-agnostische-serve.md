## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-004` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server-Logik ist transport-agnostisch (FastMCP, keine Transport-Annahmen in Tool-Handlern)
- Lifespan/Setup waere fuer alle Transports gemeinsam

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-004) verlangt die Behebung folgender Luecken:

- Keine ENV-basierte Transport-Selektion implementiert — main() ist nur mcp.run() (server.py:1004-1005), obwohl README MCP_TRANSPORT=sse dokumentiert
- Konfiguration via os.getenv im Funktionsrumpf statt Settings-Objekt (pydantic-settings)
- Kein ctx:Context-Zugriff fuer Session-Info

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/ARCH-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (ARCH-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
