## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- CHANGELOG.md im Keep-a-Changelog-Format vorhanden

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-012) verlangt die Behebung folgender Luecken:

- protocolVersion nicht explizit im Code gepinnt (FastMCP-Default)
- Keine README-Sektion 'MCP Protocol Version' / Update-Policy
- Kein Dependabot/Renovate fuer SDK-Update-PRs
- CHANGELOG hat zwei widerspruechliche [1.0.0]-Eintraege (2026-03-29 vs 2026-03-08)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-012.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-012) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
