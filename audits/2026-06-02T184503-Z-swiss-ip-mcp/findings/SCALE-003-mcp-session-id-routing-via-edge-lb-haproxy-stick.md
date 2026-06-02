## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-003) verlangt die Behebung folgender Luecken:

- Keine Edge-LB-/Mcp-Session-Id-Routing-Konfiguration im Repo (kein render.yaml, keine HAProxy/Nginx-Config)
- Abhaengig von SCALE-001: HTTP-Transport ist nicht implementiert, daher kein Session-Routing

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SCALE-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SCALE-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
