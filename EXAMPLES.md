# Use Cases & Examples — swiss-ip-mcp

Praxisnahe Anfragen nach Zielgruppe. swiss-ip-mcp gibt strukturierten, sprachgesteuerten Zugriff auf das Schweizer Immaterialgüterrechts-Register [Swissreg](https://www.swissreg.ch) des Eidgenössischen Instituts für Geistiges Eigentum (IGE/IPI): Marken, Patente, Patentpublikationen und Ergänzende Schutzzertifikate (ESZ/SPC). **API-Key nötig: Ja** — es braucht IGE-Zugangsdaten (`IGE_USERNAME` / `IGE_PASSWORD`), kostenlos nach Unterzeichnung der IGE-Nutzungsbedingungen.

## 🏫 Bildung & Schule

**«Ist ‚Learning City Zürich‘ bereits als Schweizer Marke geschützt?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_trademarks(query="Learning City Zürich*")`
Warum nützlich: Bevor eine Schule, ein Bildungsprojekt oder eine Lernplattform einen Namen öffentlich verwendet, zeigt die Markenrecherche, ob der Begriff bereits geschützt ist — beugt Namenskonflikten vor.

**«Welche Marken sind im Erziehungs-/Ausbildungssektor (Nizza-Klasse 41) registriert?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_trademarks_by_class(nice_class=41, query="Schule")`
Warum nützlich: Nizza-Klasse 41 umfasst Erziehung und Ausbildung — so lassen sich bestehende Bildungsmarken einer Branche überblicken, etwa für eine Wettbewerbs- oder Namensanalyse eines Bildungsangebots.

**«Hält die Stadt Zürich Marken beim IGE, z.B. für städtische Bildungsangebote?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_trademarks_by_owner(owner_name="Stadt Zürich*")`
Warum nützlich: Zeigt das Marken-Portfolio einer öffentlichen Trägerschaft — relevant, wenn ein Schulamt oder eine Behörde eigene Angebote schützen oder bestehende Schutzrechte prüfen will.

## 👨‍👩‍👧 Eltern & Schulgemeinde

**«Ist der Name unseres Elternvereins / Fördervereins als Marke geschützt?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_trademarks(query="Förderverein*")`
Warum nützlich: Eine Schulgemeinde oder ein Elternverein kann vor der Wahl eines Namens oder Logos prüfen, ob ähnliche Bezeichnungen bereits registriert sind — vermeidet spätere rechtliche Probleme.

**«Zu welcher Marke gehört diese Registernummer, die auf einem Produkt steht?»**
**API-Key nötig:** Ja
→ `swiss_ip_get_trademark(trademark_number="P-756123")`
Warum nützlich: Ein exakter Nummern-Lookup liefert Status, Inhaber und Waren-/Dienstleistungsklassen — nützlich, um die Herkunft einer Marke transparent nachzuvollziehen.

## 🗳️ Bevölkerung & öffentliches Interesse

**«Welche Ergänzenden Schutzzertifikate hält Novartis in der Schweiz?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_spc(query="Novartis")`
Warum nützlich: ESZ verlängern den Patentschutz für Arznei- und Pflanzenschutzmittel — von öffentlichem Interesse etwa bei Fragen zu Medikamentenpreisen und Generika-Verfügbarkeit.

**«Wie viele neue Schweizer Patente wurden im letzten Halbjahr eingetragen?»**
**API-Key nötig:** Ja
→ `swiss_ip_search_recent_filings(ip_type="patent", date_from="2026-01-01", date_to="2026-07-01")`
Warum nützlich: Der Datumsbereichs-Filter erlaubt Trend- und Zeitraumanalysen über alle Schutzrechtsarten — Grundlage für Berichterstattung über Innovationsaktivität in der Schweiz.

## 🤖 KI-Interessierte & Entwickler:innen

**«Erstelle einen IP-Überblick zu einem Unternehmen: Marken und Patente.»**
**API-Key nötig:** Ja
→ `swiss_ip_search_trademarks_by_owner(owner_name="Roche*")`
→ `swiss_ip_search_patents_by_applicant(applicant_name="Roche*")`
→ `swiss_ip_get_quota()` (verbleibendes Kontingent überwachen)
Warum nützlich: Kombiniert Marken- und Patentrecherche zu einem vollständigen IP-Profil; die Quota-Abfrage hält die Nutzung innerhalb des monatlichen IGE-Kontingents — reproduzierbar dank typisiertem Response-Envelope.

**«Portfolio-Kombination: geschützte Bezeichnung prüfen und die zugehörige Behörde amtlich benennen.»**
**API-Key nötig:** Ja (für termdat-mcp separat keine Zugangsdaten nötig)
→ `swiss_ip_search_trademarks(query="Swissmedic*")` (swiss-ip-mcp: Markenstatus)
→ danach in [`termdat-mcp`](https://github.com/malkreide/termdat-mcp): `translate_term(term="Swissmedic", from_language="DE", to_language="FR")` für die amtliche Benennung
Warum nützlich: swiss-ip-mcp klärt den markenrechtlichen Status, termdat-mcp die offizielle mehrsprachige Behördenbezeichnung — saubere Verbindung von Schutzrecht und amtlicher Terminologie.

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|---|---|---|
| Marken per Freitext suchen (Wildcard `*`) | `swiss_ip_search_trademarks` | Ja |
| Eine Marke über ihre Registernummer abrufen | `swiss_ip_get_trademark` | Ja |
| Alle Marken eines Inhabers/Anmelders finden | `swiss_ip_search_trademarks_by_owner` | Ja |
| Marken nach Nizza-Klasse (1–45) filtern | `swiss_ip_search_trademarks_by_class` | Ja |
| Patente per Freitext suchen | `swiss_ip_search_patents` | Ja |
| Ein Patent über seine Nummer abrufen | `swiss_ip_get_patent` | Ja |
| Patente nach Anmelder oder Erfinder finden | `swiss_ip_search_patents_by_applicant` | Ja |
| Offizielle Patentpublikationen durchsuchen | `swiss_ip_search_patent_publications` | Ja |
| Ergänzende Schutzzertifikate (ESZ/SPC) suchen | `swiss_ip_search_spc` | Ja |
| Eintragungen nach Datumsbereich über alle Schutzrechtsarten filtern | `swiss_ip_search_recent_filings` | Ja |
| Das verbleibende IGE-API-Kontingent prüfen | `swiss_ip_get_quota` | Ja |

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_018dMqNTA37PLHvLRGriRDmq
