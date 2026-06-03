# swiss-ip-mcp

**MCP-Server für Schweizer Immaterialgüterrechts-Daten (IGE/IPI)**

[![CI](https://github.com/malkreide/swiss-ip-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-ip-mcp/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

🇬🇧 [English version → README.md](README.md)

---

## Übersicht

`swiss-ip-mcp` ist ein [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)-Server, der KI-Modellen strukturierten, sprachgesteuerten Zugriff auf das Schweizer Schutzrechtsregister [Swissreg](https://www.swissreg.ch) des **Eidgenössischen Instituts für Geistiges Eigentum (IGE/IPI)** ermöglicht.

Er ist der Nachfolger von [`patent-mcp`](https://github.com/malkreide/patent-mcp) und deckt alle verfügbaren Domänen der [Swissreg Datadelivery API](https://www.swissreg.ch/public/apidocs/) ab: Marken, Patente, Patentpublikationen und Ergänzende Schutzzertifikate (ESZ/SPC).

**Dieser Server ist modell-agnostisch.** Er funktioniert mit Claude, GPT-4, Llama und jedem anderen MCP-kompatiblen Client – nicht nur mit Claude Desktop.

![Demo: Claude fragt das Schweizer Markenregister via swiss-ip-mcp ab](docs/assets/demo.svg)

---

## Anwendungsbeispiele

Die eigentliche Stärke liegt in der Sprachsteuerung. Statt manuell im Register zu suchen, stellt man einfach eine Frage:

> «Welche Marken hat die Stadt Zürich beim IGE eingetragen?»

> «Ist der Name ‹Lernstadt Zürich› als Marke in der Schweiz geschützt?»

> «Welche Unternehmen aus der Pharmabranche haben in den letzten sechs Monaten Schweizer Patente eingereicht?»

> «Zeig mir alle Markenanmeldungen im Bildungsbereich (Nizza-Klasse 41) seit Januar 2025.»

> «Welche ergänzenden Schutzzertifikate hält Novartis in der Schweiz?»

---

## Abgedeckte Domänen

| Domäne | Beschreibung |
|--------|-------------|
| **Marken** | Schweizer Markenregister – Anmeldung, Schutz, Inhaber, Nizza-Klassen |
| **Patente** | CH-Patente – Anmeldung, Erteilung, IPC-Klassen, Anmelder, Erfinder |
| **Patentpublikationen** | Offizielle Patentpublikationen im Schweizerischen Bundesblatt |
| **ESZ / SPC** | Ergänzende Schutzzertifikate für Arzneimittel und Pflanzenschutzmittel |

> **Hinweis:** Eine Designsuche ist in der Swissreg Datadelivery API noch nicht verfügbar.

---

## Tools (11)

| Tool | Funktion |
|------|---------|
| `swiss_ip_search_trademarks` | Markensuche nach Freitext (Wildcard `*` möglich) |
| `swiss_ip_get_trademark` | Marke anhand Registernummer abrufen |
| `swiss_ip_search_trademarks_by_owner` | Alle Marken eines Inhabers finden |
| `swiss_ip_search_trademarks_by_class` | Marken nach Nizza-Klasse filtern |
| `swiss_ip_search_patents` | Patentsuche nach Freitext |
| `swiss_ip_get_patent` | Patent anhand Nummer abrufen |
| `swiss_ip_search_patents_by_applicant` | Patente eines Anmelders oder Erfinders finden |
| `swiss_ip_search_patent_publications` | Patentpublikationen durchsuchen |
| `swiss_ip_search_spc` | ESZ/SPC-Suche (Pharma und Pflanzenschutz) |
| `swiss_ip_search_recent_filings` | Eintragungen nach Datumsbereich filtern (alle Domänen) |
| `swiss_ip_get_quota` | Verbleibendes API-Datenkontingent prüfen |

---

## Architektur

```
KI-Client (Claude Desktop, Cursor, VS Code + Continue, …)
         │
         │  MCP (stdio oder SSE)
         ▼
   swiss-ip-mcp
         │
         │  HTTPS + OAuth2 (IGE IDP)
         ▼
  Swissreg Datadelivery API
  https://www.swissreg.ch/public/api/v1
         │
         ├── TrademarkSearch
         ├── PatentSearch
         ├── PatentPublicationSearch
         ├── SPCSearch
         └── UserQuota
```

### Transportmodi

| Transport | Einsatz | Konfiguration |
|-----------|---------|---------------|
| **stdio** | Claude Desktop, lokale Entwicklung | Standard (kein Zusatzaufwand) |
| **Streamable HTTP** | Cloud-Deployment, Render.com | `MCP_TRANSPORT=streamable-http` |
| **SSE** | Legacy-HTTP-Clients | `MCP_TRANSPORT=sse` |

Der Transport wird beim Start aus der Umgebungsvariable `MCP_TRANSPORT`
gewählt (Standard `stdio`). Die HTTP-Transporte laufen unter uvicorn und
berücksichtigen:

| Variable | Standard | Zweck |
|----------|----------|-------|
| `MCP_HOST` | `127.0.0.1` | Bind-Adresse. `0.0.0.0` **nur** im Container / hinter Reverse-Proxy. |
| `PORT` / `MCP_PORT` | `8000` | Bind-Port (`PORT` gewinnt — PaaS-Konvention). |
| `MCP_ALLOWED_ORIGINS` | _(leer)_ | Komma-separierte CORS-Origin-Allow-List. Kein Wildcard in Produktion. |
| `MCP_ALLOWED_HOSTS` | _(leer)_ | Komma-separierte `Host`-Header-Allow-List; aktiviert DNS-Rebinding-Schutz. |

Der `Mcp-Session-Id`-Header wird via CORS exponiert, damit Browser-Clients ihn
lesen und bei Folge-Requests zurücksenden können.

---

## Voraussetzungen

1. **IGE-Zugangsdaten** (kostenlos): Die [Nutzungsbedingungen](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api) unterschreiben und per Post an das IGE senden. Nach Eingang erhält man Benutzername und Passwort.
2. **Python 3.11 oder neuer**
3. **`uv`** (empfohlen) oder `pip`

---

## Installation

```bash
# Direkt ausführen mit uv (empfohlen, keine lokale Installation nötig)
uvx swiss-ip-mcp

# Lokale Entwicklungsinstallation
git clone https://github.com/malkreide/swiss-ip-mcp
cd swiss-ip-mcp
pip install -e ".[dev]"
```

---

## Konfiguration

### Umgebungsvariablen

```bash
export IGE_USERNAME="dein_benutzername"
export IGE_PASSWORD="dein_passwort"
```

### Claude Desktop

Datei öffnen:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "swiss-ip": {
      "command": "uvx",
      "args": ["swiss-ip-mcp"],
      "env": {
        "IGE_USERNAME": "dein_benutzername",
        "IGE_PASSWORD": "dein_passwort"
      }
    }
  }
}
```

### Cloud / Render.com (Streamable HTTP)

```bash
MCP_TRANSPORT=streamable-http \
  MCP_HOST=0.0.0.0 PORT=8000 \
  MCP_ALLOWED_ORIGINS="https://dein-client.example" \
  MCP_ALLOWED_HOSTS="deine-app.onrender.com" \
  IGE_USERNAME=... IGE_PASSWORD=... \
  swiss-ip-mcp
```

> **Sicherheitshinweis:** `0.0.0.0` nur im Container oder hinter einem
> Reverse-Proxy binden. Für öffentliche Deployments stets `MCP_ALLOWED_ORIGINS`
> und `MCP_ALLOWED_HOSTS` setzen — das aktiviert CORS-Scoping und
> DNS-Rebinding-Schutz. Der Endpunkt ist unauthentifiziert und liefert nur
> öffentliche IP-Registerdaten; ohne vorher ergänzte Authentifizierung keine
> credential-behafteten oder nicht-öffentlichen Tools dahinter betreiben.

---

## Tests

```bash
# Unit-Tests (ohne Zugangsdaten)
PYTHONPATH=src pytest tests/ -v

# Mit Live-Tests gegen die echte API
IGE_USERNAME=... IGE_PASSWORD=... PYTHONPATH=src pytest tests/ -v
```

Der CI-Workflow läuft auf Python 3.11, 3.12 und 3.13.

---

## Observability (optional)

Der Server kann OpenTelemetry-Traces senden — ein Span pro Tool-Call plus
Child-Spans für die Backend-Aufrufe an Swissreg/IDP. Tracing ist **standardmässig
deaktiviert** und erzeugt ohne Aktivierung keinen Overhead.

```bash
pip install 'swiss-ip-mcp[otel]'

MCP_OTEL_ENABLED=1 \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://dein-collector:4318 \
  MCP_ENV=production \
  swiss-ip-mcp
```

| Variable | Zweck |
|----------|-------|
| `MCP_OTEL_ENABLED` | `1` aktiviert den Trace-Export (oder einfach den Endpunkt unten setzen). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP/HTTP-Collector-Endpunkt (Standard-OTEL-Variable). |
| `MCP_ENV` | Wert für das Resource-Attribut `deployment.environment` (Standard `production`). |

Tool-Spans enthalten ausschliesslich `mcp.tool.name` und
`mcp.tool.result.is_error` — **keine Suchargumente, Credentials oder
Antwort-Bodies**.

### Logging

Der Server loggt strukturiertes JSON auf **stderr** (stdout ist für das
stdio-Protokoll reserviert). Jeder Tool-Call bindet einen `tool`-Namen und eine
`correlation_id`, sodass alle Log-Zeilen eines Calls korreliert sind. Das Level
wird über `LOG_LEVEL` gesetzt (`DEBUG` / `INFO` / `WARNING` / `ERROR`, Standard
`INFO`):

```json
{"event": "tool.call.start", "tool": "swiss_ip_search_trademarks", "correlation_id": "da55…", "level": "info", "timestamp": "…Z"}
```

---

## MCP-Protokollversion

Die MCP-Protokollversion stammt aus dem gepinnten [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp`, via `fastmcp`) und wird gemäss Spezifikation beim `initialize` ausgehandelt — der Server einigt sich auf die höchste von beiden Seiten unterstützte Version. Mit dem aktuell gepinnten SDK ist die höchste unterstützte Version **`2025-11-25`** (ältere Clients handeln automatisch herunter). Dieser Wert folgt dem SDK und ist hier nicht fest verdrahtet.

**Update-Policy:** Die SDK-Untergrenze ist in `pyproject.toml` gepinnt; [Dependabot](.github/dependabot.yml) öffnet monatlich PRs für `mcp`-/`fastmcp`-Updates. Protokoll- oder SDK-Sprünge mit Verhaltensänderung werden in diesen PRs geprüft und in [`CHANGELOG.md`](CHANGELOG.md) dokumentiert.

---

## Datenquelle

Alle Daten stammen aus der [IGE/IPI Swissreg Datadelivery API](https://www.swissreg.ch/public/apidocs/). Die API ist nach Unterzeichnung der Nutzungsbedingungen kostenlos, unterliegt aber einem monatlichen Datentransfer-Kontingent. Das verbleibende Kontingent lässt sich jederzeit mit dem Tool `swiss_ip_get_quota` prüfen.

| Feld | Wert |
|------|------|
| Anbieter | Eidgenössisches Institut für Geistiges Eigentum (IGE/IPI) |
| Quelle | Swissreg Datadelivery API — <https://www.swissreg.ch/public/apidocs/> |
| Lizenz / Bedingungen | [IGE/IPI Swissreg Datadelivery API Terms of Use](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api) |

**Provenance:** Jede Tool-Antwort enthält einen `source`-Block (Anbieter, Quell-URL, Lizenz), damit die Attribution erhalten bleibt. Das Ergebnis-Envelope ist `{ source, total, count, match_type, results, next_page_token }`.

---

## Sicherheit & Grenzen

- **Nur-Lesen:** Alle Tools führen authentifizierte POST-Anfragen an die Swissreg API durch — es werden keine Daten geschrieben, verändert oder gelöscht.
- **Keine Personendaten:** Die API liefert öffentliche Registereinträge (Markennamen, Patentsachtitel, Anmelderorganisationen). Keine personenbezogenen Daten werden durch diesen Server verarbeitet oder gespeichert — ausser den Inhalten, die die IGE API in ihren öffentlichen Registern zurückgibt.
- **Rate Limits & Kontingent:** Die IGE Swissreg API erzwingt ein monatliches Datentransfer-Kontingent pro Account. Mit dem Tool `swiss_ip_get_quota` lässt sich das verbleibende Kontingent prüfen. Der Server erzwingt ein 60-Sekunden-Timeout pro Anfrage. Für Erkundungsabfragen empfiehlt sich `page_size` ≤ 20.
- **Authentifizierung:** Zugangsdaten (`IGE_USERNAME`, `IGE_PASSWORD`) werden zur Laufzeit aus Umgebungsvariablen gelesen und weder protokolliert noch gespeichert.
- **Nutzungsbedingungen:** Die Daten unterliegen den [Nutzungsbedingungen der IGE Swissreg Datadelivery API](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api). Für den API-Zugang ist eine unterzeichnete Nutzungsvereinbarung mit dem IGE/IPI erforderlich.
- **Keine Gewähr:** Dieses Projekt ist eine Community-Initiative ohne Verbindung zum Eidgenössischen Institut für Geistiges Eigentum (IGE/IPI). Die Verfügbarkeit hängt vom Upstream-API-Betrieb ab.

---

## Verwandte Server

| Server | Inhalt |
|--------|--------|
| [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) | Stadt Zürich Open Data (CKAN, Wetter, Parking, Geodaten) |
| [`fedlex-mcp`](https://github.com/malkreide/fedlex-mcp) | Schweizer Bundesrecht via Fedlex SPARQL |
| [`swiss-transport-mcp`](https://github.com/malkreide/swiss-transport-mcp) | ÖV-Daten, Störungen, Billette, Zugformationen |
| [`swiss-road-mobility-mcp`](https://github.com/malkreide/swiss-road-mobility-mcp) | Shared Mobility, E-Ladestationen, Verkehrsdaten |
| [`global-education-mcp`](https://github.com/malkreide/global-education-mcp) | UNESCO / OECD Bildungsdaten |
| [`patent-mcp`](https://github.com/malkreide/patent-mcp) | ⚠️ Veraltet – durch diesen Server ersetzt |

---

## Lizenz

MIT © 2026 malkreide
