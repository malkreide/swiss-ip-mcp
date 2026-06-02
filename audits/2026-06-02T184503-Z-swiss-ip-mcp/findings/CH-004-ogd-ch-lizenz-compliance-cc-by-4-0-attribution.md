## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `CH-004` |
| **PDF-Reference** | Custom (OGD-CH-Richtlinien) |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- README 'Data Source'-Sektion nennt IGE/IPI Swissreg als Quelle (README.md:187-191)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (CH-004) verlangt die Behebung folgender Luecken:

- Tool-Antworten enthalten kein source-/Lizenz-Feld pro Datensatz (Provenance geht verloren)
- Lizenzbedingungen der Daten nicht explizit benannt (nur 'terms of use'-Verweis, keine konkrete OGD/CC-Lizenz)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/CH-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (CH-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
