## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OPS-001` |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Umfangreiche Unit-Test-Suite tests/test_server.py (~30 Tests), CI laeuft pytest -m 'not live' (ci.yml)
- live-Marker in pyproject.toml registriert; Live-Tests vorhanden (TestLiveApi)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OPS-001) verlangt die Behebung folgender Luecken:

- respx ist dev-Dependency, wird aber nicht genutzt — Mocking via unittest.mock.patch von _call_api statt HTTP-Layer
- Live-Tests nutzen @pytest.mark.skipif(not LIVE) statt des registrierten @pytest.mark.live-Markers
- Kein separater nightly/manueller Live-Test-Workflow

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OPS-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (OPS-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
