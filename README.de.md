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
| **SSE** | Cloud-Deployment, Render.com | `MCP_TRANSPORT=sse` |

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

### Cloud / Render.com (SSE-Transport)

```bash
MCP_TRANSPORT=sse PORT=8000 IGE_USERNAME=... IGE_PASSWORD=... swiss-ip-mcp
```

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
