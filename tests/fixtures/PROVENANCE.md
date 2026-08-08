# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-08**.

Ohne Datum ist «gemessen» nach zwei Jahren von «angenommen» nicht mehr
zu unterscheiden — die Datei sieht gleich aus.

## Aufgezeichnet ist die Adressliste, nicht die Antwort

Die Swissreg-API verlangt Zugangsdaten; ohne sie gibt es keine Antwort,
die man datieren koennte. Pruefbar ist trotzdem, ob die Adressen, der
Realm und der Client stimmen — **und sie stimmen alle.** Das Ergebnis
ist ein Nullbefund und steht genau deshalb hier: Ohne Aufzeichnung
faengt der naechste Durchgang bei null an.

## Drei Wege, weil einer nicht getragen haette

| Messung | Antwort | Was sie traegt |
|---|---|---|
| Realm `egov`, falsche Zugangsdaten | 401 `invalid_grant` | nur die Zugangsdaten fehlen |
| KONTROLLE erfundener Realm | 404 «Realm does not exist» | `egov` existiert |
| KONTROLLE erfundener `client_id` | `invalid_client` | der Client existiert |
| `.well-known/openid-configuration` | 200, `token_endpoint` | der Realm nennt die URL selbst |
| offizielle API-Doku | nennt beide Adressen woertlich | der Endpunkt stimmt |

**Warum der letzte Weg noetig ist:** Die Swissreg-API unterscheidet
nicht. Ein POST ohne Token gibt 403, mit erfundenem Token 401 — und ein
frei erfundener Pfad unter `/public/api/` gibt jeweils dasselbe. Ein
Statuscode belegt dort nichts. Dieselbe Lage gab es bei
`epl.bag.admin.ch` in diesem Portfolio, und dort wurde aus einem 401
faelschlich «die Route existiert» geschlossen.

Das Skript bricht ab, wenn eine Kontrolle nicht mehr traegt, wenn der
Realm einen anderen Endpunkt deklariert, wenn die Doku eine der
Adressen nicht mehr nennt — oder wenn die API anfaengt zu
unterscheiden. Das Letzte waere eine gute Nachricht und trotzdem ein
Anlass, neu zu messen.

## `adressen.json`

- **Quelle:** `https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token, https://www.swissreg.ch/public/api/v1, https://www.swissreg.ch/public/apidocs/reference/authentication.html`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** die Adressliste, dreifach belegt: der Keycloak unterscheidet Realm/Client/Zugangsdaten (mit zwei Kontrollen), der Realm nennt seinen Token-Endpunkt selbst, und die offizielle Doku deklariert beide Adressen woertlich. Der dritte Weg ist noetig, weil die Swissreg-API selbst NICHT unterscheidet: gebauter und erfundener Pfad antworten identisch, ein Statuscode belegt dort also nichts
- **Groesse:** 1270 B
- **SHA-256:** `c2211eb136e5d537b2fff95b51d4470dc8290ba030d60b99c301e54a5771b336`

## NICHT aufgezeichnet

### `swissreg_*.xml`

- **Quelle:** `https://www.swissreg.ch/public/api/v1`
- **Grund:** IGE_USERNAME/IGE_PASSWORD nicht gesetzt — ohne Token gibt die API HTTP 403 bzw. 401. NICHT aufgezeichnet.

Die Antwort-Payloads stehen weiterhin als Literale im Testmodul und
sind damit **ausgedacht** — das ist der Ist-Zustand und keine
Nachlaessigkeit dieses Laufs. Wer Zugangsdaten hat, setzt
`IGE_USERNAME`/`IGE_PASSWORD` und laesst das Skript erneut laufen.

Unbelegt bleibt damit die **Form** der Antworten: ob die XML-Felder
so heissen, wie der Parser sie liest. Genau dort lagen in diesem
Portfolio die teuersten Fehler.
