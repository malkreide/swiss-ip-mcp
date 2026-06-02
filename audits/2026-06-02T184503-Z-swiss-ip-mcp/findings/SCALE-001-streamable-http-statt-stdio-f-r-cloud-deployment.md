## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-001) verlangt die Behebung folgender Luecken:

- README dokumentiert Cloud/Render-Deployment via 'MCP_TRANSPORT=sse PORT=8000 swiss-ip-mcp' (README.md:165-171) und Transport-Tabelle (README.md:100)
- Code liest WEDER MCP_TRANSPORT NOCH PORT: main() ist nur mcp.run() = stdio-Default (server.py:1004-1005)
- Der dokumentierte SSE/Cloud-Transport ist nicht implementiert — Cloud-Endpoint kann nicht auf initialize antworten
- Docstring (server.py:9) und CHANGELOG behaupten 'Streamable HTTP / SSE (Render.com)' — Dokumentations-vs-Implementierungs-Drift

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SCALE-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SCALE-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
