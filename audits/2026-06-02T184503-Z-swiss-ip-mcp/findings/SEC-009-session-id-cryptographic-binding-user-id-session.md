## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Kein Per-Client/Session-State im Code — Server läuft de facto stdio (server.py:1005)
- auth_model=none, data_class=Public Open Data — kein nutzerspezifischer Schutzbedarf

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SEC-009) verlangt die Behebung folgender Luecken:

- README bewirbt SSE/Cloud-Deployment (Render), aber es existiert keine Session-ID-Bindung an User-Identität
- Falls SSE aktiviert wuerde, kaeme nur FastMCP-Default-Session ohne kryptographische user_id:session_id-Bindung zum Einsatz
- Realrisiko niedrig wegen No-Auth + Public Data, aber inkonsistent zur beworbenen Cloud-Faehigkeit (vgl. SCALE-001)

### Risk Description

Siehe Severity `critical`. Details und Remediation im Check-Katalog
`checks/SEC-009.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SEC-009) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
