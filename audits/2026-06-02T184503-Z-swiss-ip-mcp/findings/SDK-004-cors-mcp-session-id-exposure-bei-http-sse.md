## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-004) verlangt die Behebung folgender Luecken:

- Keine CORS-Middleware konfiguriert (grep: keine cors/expose_headers/allow_origin)
- Falls SSE/HTTP aktiviert (wie in README beworben) wuerde Mcp-Session-Id nicht via expose_headers freigegeben
- Abhaengig von SCALE-001 (HTTP-Transport nicht implementiert)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SDK-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
