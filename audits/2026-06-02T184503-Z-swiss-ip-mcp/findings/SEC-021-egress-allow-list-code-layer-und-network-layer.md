## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Ausgehende Ziele sind de facto auf zwei feste Konstanten beschraenkt (server.py:36-39)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SEC-021) verlangt die Behebung folgender Luecken:

- Keine explizite Code-Layer-Egress-Allow-List (frozenset) mit assert_host_allowed-Pre-Request-Check
- Keine Network-Layer-Egress-Control dokumentiert (kein docs/network-egress.md)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SEC-021.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SEC-021) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
