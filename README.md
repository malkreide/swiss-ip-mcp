# swiss-ip-mcp

**Model Context Protocol (MCP) Server für Schweizer Immaterialgüterrechts-Daten**  
**Model Context Protocol (MCP) Server for Swiss intellectual property data**

[![CI](https://github.com/malkreide/swiss-ip-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-ip-mcp/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Deutsch

### Übersicht

`swiss-ip-mcp` ist ein MCP-Server, der KI-Modellen strukturierten Zugriff auf das Schweizer Schutzrechtsregister (Swissreg) des **Eidgenössischen Instituts für Geistiges Eigentum (IGE/IPI)** ermöglicht. Er ist der Nachfolger von `patent-mcp` und deckt alle drei Hauptdomänen der Swissreg Datadelivery API ab.

**Dieser Server ist modell-agnostisch**: Er funktioniert mit Claude, GPT-4, Llama und jedem anderen MCP-kompatiblen Client.

### Abgedeckte Domänen

| Domäne | Beschreibung |
|--------|-------------|
| **Marken** | Schweizer Markenregister – Anmeldung, Schutz, Inhaber, Nizza-Klassen |
| **Patente** | CH-Patente – Anmeldung, Erteilung, IPC-Klassen, Anmelder |
| **Patentpublikationen** | Offizielle Patentpublikationen im Schweizerischen Bundesblatt |
| **ESZ/SPC** | Ergänzende Schutzzertifikate (Pharma und Pflanzenschutz) |

### Tools (10)

| Tool | Funktion |
|------|---------|
| `swiss_ip_search_trademarks` | Markensuche nach Freitext (Wildcard `*` möglich) |
| `swiss_ip_get_trademark` | Marke anhand Nummer abrufen |
| `swiss_ip_search_trademarks_by_owner` | Marken eines Inhabers finden |
| `swiss_ip_search_trademarks_by_class` | Marken nach Nizza-Klasse filtern |
| `swiss_ip_search_patents` | Patentsuche nach Freitext |
| `swiss_ip_get_patent` | Patent anhand Nummer abrufen |
| `swiss_ip_search_patents_by_applicant` | Patente eines Anmelders finden |
| `swiss_ip_search_patent_publications` | Patentpublikationen durchsuchen |
| `swiss_ip_search_spc` | ESZ/SPC-Suche (Pharma) |
| `swiss_ip_search_recent_filings` | Eintragungen nach Datumsbereich filtern |
| `swiss_ip_get_quota` | Verbleibendes API-Kontingent prüfen |

### Voraussetzungen

1. **IGE-Zugangsdaten**: Kostenlos nach Unterzeichnung der [Nutzungsbedingungen](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api) (Formular per Post an das IGE senden).
2. **Python 3.11+**
3. **`uv`** (empfohlen) oder `pip`

### Installation

```bash
# Mit uv (empfohlen)
uvx swiss-ip-mcp

# Oder lokal entwickeln
git clone https://github.com/malkreide/swiss-ip-mcp
cd swiss-ip-mcp
pip install -e ".[dev]"
```

### Konfiguration

Umgebungsvariablen setzen:

```bash
export IGE_USERNAME="dein_benutzername"
export IGE_PASSWORD="dein_passwort"
```

#### Claude Desktop (`claude_desktop_config.json`)

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

#### Cloud / Render.com (SSE-Transport)

```bash
MCP_TRANSPORT=sse PORT=8000 IGE_USERNAME=... IGE_PASSWORD=... swiss-ip-mcp
```

### Beispiele

**Marken der Stadt Zürich finden:**
> «Welche Marken hat die Stadt Zürich beim IGE eingetragen?»

**Innovationsmonitoring:**
> «Welche Unternehmen haben in der Schweiz im Jahr 2025 Marken im Bereich Bildung (Nizza-Klasse 41) angemeldet?»

**KI-Fachgruppe Demo:**
> «Zeig mir alle Schweizer Markenanmeldungen mit dem Begriff ‹künstliche Intelligenz› der letzten 12 Monate.»

**Schulamt / Beschaffung:**
> «Ist der Name ‹Lernstadt Zürich› als Marke in der Schweiz geschützt?»

### Tests

```bash
PYTHONPATH=src pytest tests/ -v

# Mit Live-Tests (IGE-Zugangsdaten erforderlich)
IGE_USERNAME=... IGE_PASSWORD=... PYTHONPATH=src pytest tests/ -v
```

---

## English

### Overview

`swiss-ip-mcp` is an MCP server that gives AI models structured access to the Swiss intellectual property register (Swissreg) of the **Swiss Federal Institute of Intellectual Property (IGE/IPI)**. It is the successor to `patent-mcp`, covering all Swissreg Datadelivery API domains.

**This server is model-agnostic**: works with Claude, GPT-4, Llama, and any other MCP-compatible client.

### Covered Domains

| Domain | Description |
|--------|-------------|
| **Trademarks** | Swiss trademark register – filing, protection, owners, Nice classes |
| **Patents** | CH patents – filing, grant, IPC classes, applicants |
| **Patent publications** | Official patent publications in the Swiss Official Gazette |
| **SPC/ESZ** | Supplementary protection certificates (pharma & plant protection) |

### Prerequisites

1. **IGE credentials**: Free after signing the [terms of use](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api) (form sent by post to IGE).
2. **Python 3.11+**
3. **`uv`** (recommended) or `pip`

### Architecture

```
claude_desktop_config.json
         │
         ▼
   swiss-ip-mcp (stdio / SSE)
         │
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

### Transport Selection

| Transport | Use case | Config |
|-----------|----------|--------|
| **stdio** | Claude Desktop, local use | Default |
| **SSE** | Cloud deployment (Render.com etc.) | `MCP_TRANSPORT=sse` |

### Data Source

All data is provided by the [IGE/IPI Swissreg Datadelivery API](https://www.swissreg.ch/public/apidocs/). The API is free after registration, subject to a monthly data transfer quota.

---

## Verwandte Server / Related Servers

| Server | Beschreibung |
|--------|-------------|
| [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) | Stadt Zürich Open Data |
| [`fedlex-mcp`](https://github.com/malkreide/fedlex-mcp) | Schweizer Bundesrecht |
| [`swiss-transport-mcp`](https://github.com/malkreide/swiss-transport-mcp) | ÖV und Mobilitätsdaten |
| [`global-education-mcp`](https://github.com/malkreide/global-education-mcp) | UNESCO / OECD Bildungsdaten |

---

## Lizenz / License

MIT © 2026 malkreide
