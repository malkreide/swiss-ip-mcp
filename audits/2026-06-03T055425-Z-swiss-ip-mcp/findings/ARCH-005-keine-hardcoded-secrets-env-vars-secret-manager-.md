## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Secrets via os.getenv, keine hardcoded Secrets (server.py:129-130)
- .gitignore vorhanden inkl. .env/.env.* (PR #2)
- .env.example mit Platzhaltern vorhanden (PR #3)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-005) verlangt die Behebung folgender Luecken:

- Secrets weiterhin als plain str, nicht pydantic SecretStr (low)
- Kein Gitleaks/Trufflehog-Secret-Scanning in CI (low)

### Risk Description

Siehe Severity `critical`. Details und Remediation im Check-Katalog
`checks/ARCH-005.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-005) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
