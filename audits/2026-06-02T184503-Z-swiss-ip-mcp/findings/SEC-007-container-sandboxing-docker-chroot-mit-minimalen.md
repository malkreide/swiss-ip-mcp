## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Read-only, keine Filesystem-Tools — geringe Sandboxing-Anforderung

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SEC-007) verlangt die Behebung folgender Luecken:

- Kein Dockerfile im Repo — keine USER-non-root/Privilege-Drop/readOnlyRootFilesystem-Haertung
- Cloud-Deployment (Render) wird beworben, verlaesst sich aber undokumentiert auf Plattform-Defaults

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SEC-007.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SEC-007) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
