# MCP-Server Audit-Report — `swiss-ip-mcp`

**Audit-Datum:** 2026-06-02
**Skill-Version:** 1.0.0
**Catalog-Version:** 2026-04

---

## 1. Executive Summary

Server `swiss-ip-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 18 bestanden, 26 Findings dokumentiert (2 critical, 13 high, 11 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SCALE-001, SDK-001.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-ip-mcp` |
| Audit-Datum | 2026-06-02 |
| Skill-Version | 1.0.0 |
| Catalog-Version | 2026-04 |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'Render']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 5 | 0 | 6 | 0 | 0 |
| CH | 0 | 0 | 1 | 0 | 0 |
| OBS | 1 | 1 | 3 | 0 | 0 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 0 | 1 | 4 | 0 | 0 |
| SDK | 0 | 1 | 3 | 0 | 0 |
| SEC | 11 | 0 | 4 | 0 | 0 |
| **Total** | **18** | **3** | **23** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-009 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-001 | SCALE | high | fail |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SDK-001 | SDK | high | fail |
| SDK-004 | SDK | high | partial |
| SEC-007 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-008 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| CH-004 | CH | medium | partial |
| OBS-003 | OBS | medium | partial |
| OBS-006 | OBS | medium | fail |
| SCALE-004 | SCALE | medium | partial |
| SCALE-006 | SCALE | medium | partial |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 26 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-002` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Detaillierte Docstrings > 100 Zeichen mit Args/Returns und Beispielen (z.B. server.py:562-575)
- Differenzierung aehnlicher Tools explizit (search vs by_owner vs by_class)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-002) verlangt die Behebung folgender Luecken:

- Keine strukturierten <use_case>/<important_notes>-XML-Tags in den Tool-Beschreibungen (nur Prosa)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Not-Found-Meldungen enthalten actionable Hinweis zum Nummernformat (server.py:657-659, 785-789)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-003) verlangt die Behebung folgender Luecken:

- Negatives 'nicht gefunden'-Framing ohne match_type-Feld
- Keine Fuzzy-Match-/Suggestion-Mechanik bei leeren Suchergebnissen der Search-Tools

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-004` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server-Logik ist transport-agnostisch (FastMCP, keine Transport-Annahmen in Tool-Handlern)
- Lifespan/Setup waere fuer alle Transports gemeinsam

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-004) verlangt die Behebung folgender Luecken:

- Keine ENV-basierte Transport-Selektion implementiert — main() ist nur mcp.run() (server.py:1004-1005), obwohl README MCP_TRANSPORT=sse dokumentiert
- Konfiguration via os.getenv im Funktionsrumpf statt Settings-Objekt (pydantic-settings)
- Kein ctx:Context-Zugriff fuer Session-Info

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/ARCH-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (ARCH-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### ARCH-005

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


### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server nutzt das Tools-Primitiv sauber und konsistent

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-008) verlangt die Behebung folgender Luecken:

- Nur Tools verwendet — keine Resources oder Prompts
- Read-only-Lookups (z.B. get_trademark/get_patent) sind Resource-Migrations-Kandidaten; keine dokumentierte Begruendung fuer Tools-only

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-008.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (ARCH-008) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- CHANGELOG.md im Keep-a-Changelog-Format vorhanden

### Gaps / Expected Behavior

Der Best-Practice-Katalog (ARCH-012) verlangt die Behebung folgender Luecken:

- protocolVersion nicht explizit im Code gepinnt (FastMCP-Default)
- Keine README-Sektion 'MCP Protocol Version' / Update-Policy
- Kein Dependabot/Renovate fuer SDK-Update-PRs
- CHANGELOG hat zwei widerspruechliche [1.0.0]-Eintraege (2026-03-29 vs 2026-03-08)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/ARCH-012.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (ARCH-012) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### CH-004

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


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-001` |
| **PDF-Reference** | Sec 6.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Jeder Tool-Handler faengt Exceptions ab und liefert {"error": ...} (z.B. server.py:585-586)
- Test deckt Execution-Error-Pfad ab (test_search_trademarks_api_error, test_get_trademark_not_found)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-001) verlangt die Behebung folgender Luecken:

- Fehler werden als normales String-Result {"error":...} zurueckgegeben, NICHT mit MCP isError:true — LLM kann Fehler nicht von Erfolg unterscheiden
- Kein Test fuer Protocol-Level-Error-Pfad (falsches Tool/Args)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OBS-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (OBS-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- _handle_error liefert benutzerfreundliche Meldungen fuer 401/403/429/Timeout (server.py:291-315)
- Keine traceback.format_exc()-Ausgabe an den Client

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-002) verlangt die Behebung folgender Luecken:

- Generischer Zweig leakt Exception-Typ und -Message an den Client: f'Unerwarteter Fehler ({type(e).__name__}): {e}' (server.py:315)
- API-Fehler leakt rohen Upstream-Body an LLM: e.response.text[:500] (server.py:312)
- mask_error_details=True nicht in FastMCP-Init gesetzt (server.py:330)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OBS-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OBS-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Logging vorhanden via stdlib logging (server.py:30-31)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-003) verlangt die Behebung folgender Luecken:

- Kein strukturierter Logger (structlog/loguru) — kein JSON/logfmt-Output
- Nur info-Level aktiv genutzt (1 Aufruf), keine 4 Severity-Stufen
- Kein per-Tool-Call gebundener Kontext (tool name, session_id, correlation_id)

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/OBS-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OBS-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OBS-006) verlangt die Behebung folgender Luecken:

- Keine OpenTelemetry-Integration (kein opentelemetry-Dependency, keine TracerProvider/OTLP-Exporter)
- Keine httpx-Auto-Instrumentation, keine per-Tool-Call-Spans

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/OBS-006.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (OBS-006) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### OPS-001

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


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `OPS-003` |
| **PDF-Reference** | Anhang C4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Server ist konsistent Phase 1 (read-only): alle Tools readOnlyHint=true, keine destruktiven Tools

### Gaps / Expected Behavior

Der Best-Practice-Katalog (OPS-003) verlangt die Behebung folgender Luecken:

- Keine explizite Phasen-Deklaration (Phase 1/2/3) im README
- Kein roadmap-File mit phasenspezifischen Tasks

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/OPS-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (OPS-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SCALE-001

## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-001) verlangt die Behebung folgender Luecken:

- README dokumentiert Cloud/Render-Deployment via 'MCP_TRANSPORT=sse PORT=8000 swiss-ip-mcp' (README.md:165-171) und Transport-Tabelle (README.md:100)
- Code liest WEDER MCP_TRANSPORT NOCH PORT: main() ist nur mcp.run() = stdio-Default (server.py:1004-1005)
- Der dokumentierte SSE/Cloud-Transport ist nicht implementiert — Cloud-Endpoint kann nicht auf initialize antworten
- Docstring (server.py:9) und CHANGELOG behaupten 'Streamable HTTP / SSE (Render.com)' — Dokumentations-vs-Implementierungs-Drift

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SCALE-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SCALE-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SCALE-002

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


### SCALE-003

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


### SCALE-004

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


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Per-Request-Timeout REQUEST_TIMEOUT=60.0 gesetzt (server.py:49) — eine Resource-Control

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SCALE-006) verlangt die Behebung folgender Luecken:

- Keine Memory-/CPU-/FD-Limits konfiguriert (keine Container-Resource-Config im Repo)
- Kein dokumentiertes OOM-/Restart-Verhalten

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SCALE-006.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SCALE-006) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SDK-001

## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | fail |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-001) verlangt die Behebung folgender Luecken:

- Keine Lifespan-Funktion (@asynccontextmanager) definiert; FastMCP-Konstruktor erhaelt kein lifespan= (server.py:330-339)
- _call_api erzeugt pro Tool-Call eine neue httpx.AsyncClient()-Instanz (server.py:97) — kein Connection-Pooling, neue TCP/TLS-Handshakes je Request
- Verletzt explizit das Pass-Kriterium 'Keine httpx.AsyncClient() pro Tool-Call'

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SDK-001.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-001) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Pydantic >= 2.0 in dependencies; Input-Models exzellent typisiert
- StrEnum ResponseFormat fuer enumerable Werte (server.py:322-324)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-002) verlangt die Behebung folgender Luecken:

- Tools geben rohen json.dumps-String zurueck (-> str), keine strukturierten BaseModel/TypedDict/Dataclass-Return-Typen (z.B. server.py:584)
- Response-Envelope (total/count/items/next_page_token) ohne source/provenance-Felder

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SDK-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Kurze, klar abgegrenzte Tool-Handler

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-003) verlangt die Behebung folgender Luecken:

- Kein Tool nutzt ctx:Context — API-Calls bis zu 60s ohne ctx.report_progress()
- response_format-Parameter (markdown/json) wird akzeptiert, aber ignoriert — Tools liefern immer json.dumps (z.B. server.py:584), 'markdown' nie erzeugt

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SDK-003.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-003) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-004) verlangt die Behebung folgender Luecken:

- Keine CORS-Middleware konfiguriert (grep: keine cors/expose_headers/allow_origin)
- Falls SSE/HTTP aktiviert (wie in README beworben) wuerde Mcp-Session-Id nicht via expose_headers freigegeben
- Abhaengig von SCALE-001 (HTTP-Transport nicht implementiert)

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SDK-004.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-004) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


### SEC-007

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


### SEC-009

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


### SEC-021

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


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Alle Tools tragen konsistentes Namespace-Praefix mit Server-Identitaet (swiss_ip_*, z.B. server.py:552)
- CHANGELOG listet Tool-Definitionen explizit

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SEC-022) verlangt die Behebung folgender Luecken:

- Kein Tool-Definition-Hash-Snapshot im Repo (kein Rug-Pull-Schutz)
- Praefix nutzt einfaches _ statt der empfohlenen <server>__<tool>-Doppelunterstrich-Konvention

### Risk Description

Siehe Severity `high`. Details und Remediation im Check-Katalog
`checks/SEC-022.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

M

### Verification After Fix

- Re-Audit dieses Checks (SEC-022) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-009** (critical, partial)
3. **ARCH-004** (high, partial)
4. **OBS-001** (high, partial)
5. **OBS-002** (high, partial)
6. **OPS-001** (high, partial)
7. **OPS-003** (high, partial)
8. **SCALE-001** (high, fail)
9. **SCALE-002** (high, partial)
10. **SCALE-003** (high, partial)
11. **SDK-001** (high, fail)
12. **SDK-004** (high, partial)
13. **SEC-007** (high, partial)
14. **SEC-021** (high, partial)
15. **SEC-022** (high, partial)
16. **ARCH-002** (medium, partial)
17. **ARCH-003** (medium, partial)
18. **ARCH-008** (medium, partial)
19. **ARCH-012** (medium, partial)
20. **CH-004** (medium, partial)
21. **OBS-003** (medium, partial)
22. **OBS-006** (medium, fail)
23. **SCALE-004** (medium, partial)
24. **SCALE-006** (medium, partial)
25. **SDK-002** (medium, partial)
26. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `2026-04` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-06-02` |


_Generated by tools/build_report.py — do not edit by hand._
