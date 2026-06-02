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

- src/swiss_ip_mcp/server.py:59-60 — Credentials via os.getenv(IGE_USERNAME/IGE_PASSWORD), keine hardcoded Secrets
- Default-Wert ist Leerstring, kein echtes Secret (server.py:59)
- README.md:198 — 'Credentials read from env vars at runtime and never logged or persisted'

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-005) verlangt die Behebung folgender Luecken:

- Kein .gitignore im Repo — .env-Dateien sind nicht vor versehentlichem Commit geschützt
- Keine .env.example mit Platzhaltern
- Secrets als plain str gehalten, nicht pydantic SecretStr
- Kein Gitleaks/Trufflehog-Secret-Scanning in CI

### Risk Description

Siehe Severity `critical`. Details und Remediation im Check-Katalog
`checks/ARCH-005.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-005) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
