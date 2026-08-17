#!/usr/bin/env python3
"""Prueft die Adressliste — ohne Zugangsdaten, mit Kontrollen.

    python scripts/record_fixtures.py

WARUM ES DAS GIBT. Ein handgeschriebener Mock kodiert die Annahme seines
Autors und kann sie deshalb prinzipiell nicht widerlegen: Produktivcode und
Fixture stammen aus demselben Kopf. Wo beide irren, irren beide gleich, und
die Suite bleibt gruen.

Dieser Server verlangt `IGE_USERNAME`/`IGE_PASSWORD`. Ohne sie gibt es keine
Antwort der Swissreg-API, die man datieren koennte — `PROVENANCE.md` fuehrt
diese Payloads deshalb ausdruecklich als NICHT AUFGEZEICHNET.

WAS AUCH OHNE SCHLUESSEL PRUEFBAR IST, ist die Adressliste. Und zwar
vollstaendig: Ergebnis am 2026-08-08 ist ein **Nullbefund** — jede Adresse,
jeder Realm und jeder Client, die dieser Server baut, sind die, die die Quelle
fuehrt. Das ist eine gute Nachricht und gehoert trotzdem festgehalten; ohne
Aufzeichnung faengt der naechste Durchgang bei null an.

WIE ES BELEGT IST — drei unabhaengige Wege, weil einer nicht getragen haette:

1. **Der Realm antwortet unterschiedlich.** `.../realms/egov/...` mit falschen
   Zugangsdaten -> HTTP 401 `invalid_grant` («Invalid user credentials»). Ein
   erfundener Realm -> HTTP 404 «Realm does not exist». Ein erfundener
   `client_id` -> `invalid_client`. Der Keycloak unterscheidet also drei
   Faelle, und der konfigurierte Client faellt in den, bei dem nur die
   Zugangsdaten fehlen.

2. **Der Realm nennt seinen Token-Endpunkt selbst.**
   `.../realms/egov/.well-known/openid-configuration` liefert HTTP 200 und
   darin `token_endpoint` — identisch mit der gebauten URL. Ein erfundener
   Realm liefert dort 404.

3. **Die offizielle API-Doku deklariert beide Adressen woertlich.**
   `swissreg.ch/public/apidocs/reference/authentication.html` nennt die
   Token-URL, den `client_id` als «constant string» und
   `https://www.swissreg.ch/public/api/v1`.

WARUM DER DRITTE WEG NOETIG WAR. Die Swissreg-API selbst **unterscheidet
nicht**: Ein POST ohne Token liefert HTTP 403, mit erfundenem Token HTTP 401 —
und ein frei erfundener Pfad unter `/public/api/` liefert jeweils dasselbe.
Ein Statuscode belegt dort also nichts. Genau dieselbe Lage gab es bei
`epl.bag.admin.ch` in diesem Portfolio, und dort wurde daraus faelschlich
«die Route existiert» geschlossen.

Ohne Aufzeichnungsdatum ist «gemessen» nach zwei Jahren von «angenommen» nicht
mehr zu unterscheiden.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))

# Aus dem Produktivcode, nicht aus einer Abschrift.
from swiss_ip_mcp.server import API_ENDPOINT, CLIENT_ID, IDP_TOKEN_URL  # noqa: E402

DOKU = "https://www.swissreg.ch/public/apidocs/reference/authentication.html"
WELL_KNOWN = IDP_TOKEN_URL.replace("/protocol/openid-connect/token", "/.well-known/openid-configuration")
ERFUNDENER_REALM = IDP_TOKEN_URL.replace("/realms/egov/", "/realms/diesen-realm-gibt-es-nicht/")


def record() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict] = []
    skipped: list[dict] = []

    def write(name: str, payload: object, url: str, rule: str) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        (FIXTURES / name).write_text(text, encoding="utf-8")
        entries.append(
            {
                "name": name,
                "url": url,
                "rule": rule,
                "bytes": len(text.encode("utf-8")),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        print(f"ok  {name:<26} {len(text.encode('utf-8')):>7} B")

    def fehler(r: httpx.Response) -> str:
        try:
            return str(r.json().get("error", ""))
        except Exception:
            return ""

    with httpx.Client(timeout=90.0, follow_redirects=True) as c:
        # -- 1) Der Realm und der Client, mit zwei Kontrollen ----------------
        grund = {"grant_type": "password", "username": "kein-echter-nutzer", "password": "kein-echtes-passwort"}
        proben = {
            "gebaut": (IDP_TOKEN_URL, {**grund, "client_id": CLIENT_ID}),
            "kontrolle_erfundener_client": (
                IDP_TOKEN_URL,
                {**grund, "client_id": "diesen-client-gibt-es-nicht"},
            ),
            "kontrolle_erfundener_realm": (ERFUNDENER_REALM, {**grund, "client_id": CLIENT_ID}),
        }
        idp: dict[str, dict] = {}
        for label, (url, daten) in proben.items():
            r = c.post(url, data=daten)
            idp[label] = {"url": url, "status": r.status_code, "error": fehler(r)}
            print(f"    {r.status_code}  {label:<28} {fehler(r)}")

        if idp["kontrolle_erfundener_realm"]["status"] != 404:
            raise SystemExit(
                "Ein erfundener Realm antwortet nicht mehr mit 404 — ohne diese "
                "Kontrolle belegt die Messung nicht, dass `egov` existiert."
            )
        if idp["kontrolle_erfundener_client"]["error"] != "invalid_client":
            raise SystemExit(
                "Ein erfundener client_id liefert nicht mehr `invalid_client` — "
                "ohne diese Kontrolle laesst sich «Client existiert» nicht von "
                "«Zugangsdaten fehlen» trennen."
            )
        if idp["gebaut"]["error"] != "invalid_grant":
            raise SystemExit(
                f"Der konfigurierte Client liefert `{idp['gebaut']['error']}` statt "
                "`invalid_grant`. Das heisst NICHT mehr «nur die Zugangsdaten "
                "fehlen» — der Befund gehoert neu gemessen."
            )

        # -- 2) Der Realm nennt seinen Token-Endpunkt selbst ----------------
        wk = c.get(WELL_KNOWN)
        wk.raise_for_status()
        deklariert = wk.json().get("token_endpoint")
        if deklariert != IDP_TOKEN_URL:
            raise SystemExit(f"Der Realm deklariert {deklariert}, der Server baut {IDP_TOKEN_URL}.")

        # -- 3) Die API unterscheidet NICHT — deshalb die Doku --------------
        xml = b'<?xml version="1.0"?><Request/>'
        kopf = {"Content-Type": "application/xml", "Accept": "application/xml"}
        api = {}
        for label, url in (
            ("gebaut", API_ENDPOINT),
            ("kontrolle_erfundener_pfad", "https://www.swissreg.ch/public/api/diesen-pfad-gibt-es-nicht"),
        ):
            r = c.post(url, content=xml, headers=kopf)
            api[label] = {"url": url, "status_ohne_token": r.status_code}
            print(f"    {r.status_code}  api {label}")
        if api["gebaut"]["status_ohne_token"] != api["kontrolle_erfundener_pfad"]["status_ohne_token"]:
            raise SystemExit(
                "Die API unterscheidet jetzt zwischen gebautem und erfundenem "
                "Pfad — dann laesst sie sich direkt pruefen, und der Umweg ueber "
                "die Doku gehoert ersetzt. Gute Nachricht, aber neu zu messen."
            )

        doku = c.get(DOKU)
        doku.raise_for_status()
        text = doku.text
        deklarationen = {
            "token_url": IDP_TOKEN_URL in text,
            "client_id": CLIENT_ID in text,
            "api_endpoint": API_ENDPOINT in text,
            "grant_type_password": bool(re.search(r"grant_type\s*=\s*password", text)),
        }
        fehlt = sorted(k for k, v in deklarationen.items() if not v)
        if fehlt:
            raise SystemExit(
                f"Die offizielle Doku nennt diese Werte nicht mehr: {fehlt}. Da "
                "die API selbst nicht unterscheidet, ist sie der einzige Beleg — "
                "ohne sie ist die Adressliste unbelegt."
            )

        write(
            "adressen.json",
            {
                "recorded_at": recorded_at,
                "idp": idp,
                "realm_deklariert_token_endpoint": deklariert,
                "api": api,
                "doku_deklariert": deklarationen,
                "doku_url": DOKU,
                "befund": "Nullbefund — jede gebaute Adresse ist die, die die Quelle fuehrt",
            },
            f"{IDP_TOKEN_URL}, {API_ENDPOINT}, {DOKU}",
            "die Adressliste, dreifach belegt: der Keycloak unterscheidet "
            "Realm/Client/Zugangsdaten (mit zwei Kontrollen), der Realm nennt "
            "seinen Token-Endpunkt selbst, und die offizielle Doku deklariert "
            "beide Adressen woertlich. Der dritte Weg ist noetig, weil die "
            "Swissreg-API selbst NICHT unterscheidet: gebauter und erfundener "
            "Pfad antworten identisch, ein Statuscode belegt dort also nichts",
        )

    if not os.environ.get("IGE_PASSWORD"):
        skipped.append(
            {
                "name": "swissreg_*.xml",
                "url": API_ENDPOINT,
                "why": "IGE_USERNAME/IGE_PASSWORD nicht gesetzt — ohne Token gibt "
                "die API HTTP 403 bzw. 401. NICHT aufgezeichnet.",
            }
        )
        print("--  swissreg_*.xml            uebersprungen (keine Zugangsdaten)")

    _write_provenance(recorded_at, entries, skipped)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict], skipped: list[dict]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}**.",
        "",
        "Ohne Datum ist «gemessen» nach zwei Jahren von «angenommen» nicht mehr",
        "zu unterscheiden — die Datei sieht gleich aus.",
        "",
        "## Aufgezeichnet ist die Adressliste, nicht die Antwort",
        "",
        "Die Swissreg-API verlangt Zugangsdaten; ohne sie gibt es keine Antwort,",
        "die man datieren koennte. Pruefbar ist trotzdem, ob die Adressen, der",
        "Realm und der Client stimmen — **und sie stimmen alle.** Das Ergebnis",
        "ist ein Nullbefund und steht genau deshalb hier: Ohne Aufzeichnung",
        "faengt der naechste Durchgang bei null an.",
        "",
        "## Drei Wege, weil einer nicht getragen haette",
        "",
        "| Messung | Antwort | Was sie traegt |",
        "|---|---|---|",
        "| Realm `egov`, falsche Zugangsdaten | 401 `invalid_grant` | nur die Zugangsdaten fehlen |",
        "| KONTROLLE erfundener Realm | 404 «Realm does not exist» | `egov` existiert |",
        "| KONTROLLE erfundener `client_id` | `invalid_client` | der Client existiert |",
        "| `.well-known/openid-configuration` | 200, `token_endpoint` | der Realm nennt die URL selbst |",
        "| offizielle API-Doku | nennt beide Adressen woertlich | der Endpunkt stimmt |",
        "",
        "**Warum der letzte Weg noetig ist:** Die Swissreg-API unterscheidet",
        "nicht. Ein POST ohne Token gibt 403, mit erfundenem Token 401 — und ein",
        "frei erfundener Pfad unter `/public/api/` gibt jeweils dasselbe. Ein",
        "Statuscode belegt dort nichts. Dieselbe Lage gab es bei",
        "`epl.bag.admin.ch` in diesem Portfolio, und dort wurde aus einem 401",
        "faelschlich «die Route existiert» geschlossen.",
        "",
        "Das Skript bricht ab, wenn eine Kontrolle nicht mehr traegt, wenn der",
        "Realm einen anderen Endpunkt deklariert, wenn die Doku eine der",
        "Adressen nicht mehr nennt — oder wenn die API anfaengt zu",
        "unterscheiden. Das Letzte waere eine gute Nachricht und trotzdem ein",
        "Anlass, neu zu messen.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Quelle:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']}",
            f"- **Groesse:** {e['bytes']} B",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    if skipped:
        lines += ["## NICHT aufgezeichnet", ""]
        for s in skipped:
            lines += [f"### `{s['name']}`", "", f"- **Quelle:** `{s['url']}`", f"- **Grund:** {s['why']}", ""]
        lines += [
            "Die Antwort-Payloads stehen weiterhin als Literale im Testmodul und",
            "sind damit **ausgedacht** — das ist der Ist-Zustand und keine",
            "Nachlaessigkeit dieses Laufs. Wer Zugangsdaten hat, setzt",
            "`IGE_USERNAME`/`IGE_PASSWORD` und laesst das Skript erneut laufen.",
            "",
            "Unbelegt bleibt damit die **Form** der Antworten: ob die XML-Felder",
            "so heissen, wie der Parser sie liest. Genau dort lagen in diesem",
            "Portfolio die teuersten Fehler.",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(record())
    except httpx.HTTPError as exc:
        print(f"FEHLER: Quelle nicht erreichbar: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
