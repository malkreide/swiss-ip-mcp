## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Distribution via PyPI/uvx (uvx swiss-ip-mcp) — Container nicht zwingend

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-004) verlangt die Behebung folgender Luecken:

- Kein Dockerfile (kein Multi-Stage-Build, kein -slim Base, kein non-root USER, kein HEALTHCHECK)
- Cloud-Deployment verlaesst sich auf Plattform-Buildpack ohne dokumentierte Image-Haertung

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SCALE-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SCALE-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
