## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Stdio-Default ist zustandslos (kein LB-Bedarf in der real funktionierenden Variante)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-002) verlangt die Behebung folgender Luecken:

- Beworbenes SSE/Cloud-Deployment hat keine Sticky-Session-/Shared-State-Strategie (abhaengig von SCALE-001, Transport nicht implementiert)
- Keine Session-TTL/Failover-Konfiguration im Repo

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SCALE-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SCALE-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
