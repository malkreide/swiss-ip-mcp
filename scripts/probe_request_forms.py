#!/usr/bin/env python3
"""Welche Anfrageform nimmt swissreg.ch an — gemessen, nicht geraten.

WARUM
-----
Nach dem Umbau der Antwort-Auswertung (PR #95) blieben drei Fragen offen, und
alle drei sitzen auf der ANFRAGE-Seite. Gemessen am 4.10.2026:

  - **Nummernsuche:** Eine echte Anmeldenummer aus einem Suchtreffer, in
    `<Id>` gestellt, ergab `TotalItemCount 0`. Die Doku kennt `Id` nur als
    «article identifier, StringType» und verweist aufs XSD.
  - **Pagination:** Der Token aus `Continuations/Continuation` wirkt als
    `<Page token="...">` nicht — Seite 2 trug dieselben Saetze wie Seite 1.
    Die Doku sagt, warum: `Continuation` gehoert zur `AbstractAction`-Gruppe
    und wird als ganzes Element in die naechste `ApiRequest` kopiert.
  - **Publikationssuche:** Die Quelle antwortet mit
    `could not parse the action PatentPublicationSearch`.

Raten hilft bei keiner davon. Dieses Skript stellt die Formen nebeneinander
und berichtet, was die Quelle auf jede sagt.

WAS BERICHTET WIRD — UND WAS NICHT
----------------------------------
Je Form: wie sie gebildet wurde, `success`, `TotalItemCount`, Satzzahl und
gegebenenfalls der Log-Code. **Nicht** der Wert, mit dem gesucht wurde: Die
Nummern stammen aus einem echten Datensatz, und ihr Wortlaut gehoert nicht in
ein Workflow-Log. Berichtet wird die Herkunft («RegistrationNumber ohne
fuehrende Nullen») plus Laenge — das genuegt, um die richtige Form zu
erkennen, und `tests/fixtures/live/` traegt die Form ohnehin schon.

Fehlermeldungen der Quelle werden im Wortlaut berichtet: Sie beziehen sich auf
die eigene Anfrage.

AUFRUF
------
Braucht `IGE_USERNAME` und `IGE_PASSWORD`; laeuft im Workflow
`shape-probe.yml` mit `mode: anfrageformen`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import xml.etree.ElementTree as ET

# Kandidaten fuer den Action-Typ der Publikationssuche. Der erste ist der, den
# der Server heute schickt und den die Quelle ablehnt; er steht als Kontrolle
# mit in der Liste, damit die Messung ihre eigene Nulllinie zeigt.
PUBLIKATION_ACTIONS = [
    "PatentPublicationSearch",
    "PublicationSearch",
    "PatentPublicationsSearch",
    "PatPublicationSearch",
]


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def befund(root: ET.Element) -> str:
    """Eine Zeile: success, Zaehler, Satzzahl, Log — ohne Inhalte."""
    result = next((el for el in root.iter() if _local(el.tag) == "Result"), None)
    if result is None:
        return "keine Result-Antwort"
    success = result.get("success")
    total = next(((el.text or "").strip() for el in root.iter() if _local(el.tag) == "TotalItemCount"), "-")
    saetze = sum(1 for kind in result if (kind.get("role") or "") == "item")
    logs = [
        f"{el.get('level')}/{el.get('code')}: {(el.text or '').strip()}"
        for el in root.iter()
        if _local(el.tag) == "LogEntry"
    ]
    teile = [f"success={success}", f"total={total}", f"saetze={saetze}"]
    if logs:
        teile.append("log=" + " | ".join(logs))
    return "  ".join(teile)


def id_kandidaten(satz: ET.Element) -> list[tuple[str, str]]:
    """(Beschreibung, Wert) — alle aus einem echten Datensatz abgeleitet.

    Nichts erfunden: Wer eine Nummer erfindet, misst das Format nicht, sondern
    nur, dass die Nummer nicht existiert.
    """

    def text(name: str) -> str:
        return next(
            ((el.text or "").strip() for el in satz.iter() if _local(el.tag) == name and (el.text or "").strip()),
            "",
        )

    anmelde = text("ApplicationNumberText")
    register = text("RegistrationNumber")
    amt = text("RegistrationOfficeCode") or "CH"

    kandidaten: list[tuple[str, str]] = []
    if anmelde:
        kandidaten += [
            ("ApplicationNumberText unveraendert", anmelde),
            ("ApplicationNumberText ohne fuehrende Nullen", anmelde.lstrip("0") or anmelde),
            (f"Amtscode + ApplicationNumberText ({amt})", f"{amt}{anmelde}"),
        ]
    if register:
        kandidaten += [
            ("RegistrationNumber unveraendert", register),
            ("RegistrationNumber ohne fuehrende Nullen", register.lstrip("0") or register),
            (f"Amtscode + RegistrationNumber ({amt})", f"{amt}{register}"),
            ("P- + RegistrationNumber", f"P-{register}"),
        ]
    return kandidaten


NS_PUB = "urn:ige:schema:xsd:datadeliverypatentpublication-1.0.0"


def publikations_rumpfe(ns_core: str, ns_common: str, ns_pat: str) -> list[tuple[str, str]]:
    """(Beschreibung, vollstaendige Anfrage) je Rumpf-Variante.

    Als Modulfunktion, nicht als Schleife im Messlauf: Eine Liste von Tupeln
    verschiedener Laenge faellt sonst erst in der CI auf, mit Zugangsdaten und
    nach zwei Minuten Wartezeit — am 4.10.2026 genau so passiert
    (`ValueError: too many values to unpack`, Lauf 37204275286). `praefix`
    wird jetzt aus der Variante abgeleitet und nicht danebengelegt, wo es
    auseinanderlaufen kann.
    """
    varianten = [
        ("pat: (heute)", "pat:"),
        ("ohne Praefix, common", ""),
        ("eigener Publikations-Namespace", "pub:"),
    ]
    out = []
    for beschreibung, praefix in varianten:
        element = f"{praefix}PatentPublicationSearchRequest"
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<ApiRequest xmlns="{ns_core}" xmlns:pat="{ns_pat}" xmlns:pub="{NS_PUB}">\n'
            '  <Action type="PatentPublicationSearch">\n'
            f'    <{element} xmlns="{ns_common}">\n'
            '      <Representation details="Maximal"/>\n'
            '      <Page size="3"/>\n'
            "      <Query><Any>Roche*</Any></Query>\n"
            f"    </{element}>\n"
            "  </Action>\n"
            "</ApiRequest>"
        )
        out.append((beschreibung, xml))
    return out


async def _messen(was: str) -> int:
    import swiss_ip_mcp.server as srv
    from swiss_ip_mcp.server import (
        NS_COMMON,
        NS_CORE,
        NS_PAT,
        _build_trademark_search,
        _call_api,
        _esc,
    )

    gemessen = 0

    if was in ("alle", "id"):
        print("\n=== Nummernsuche: welche Id-Form findet den Satz? ===")
        erste = await _call_api(_build_trademark_search("<Any>Zürich*</Any>", 3))
        result = next(el for el in erste.iter() if _local(el.tag) == "Result")
        saetze = [kind for kind in result if (kind.get("role") or "") == "item"]
        if not saetze:
            print("Kein Satz als Ausgangspunkt — Messung entfaellt", file=sys.stderr)
        else:
            kandidaten = id_kandidaten(saetze[0])
            print(f"{len(kandidaten)} Form(en), alle aus einem echten Satz abgeleitet.\n")
            for beschreibung, wert in kandidaten:
                xml = _build_trademark_search(f"<Id>{_esc(wert)}</Id>", 3)
                try:
                    root = await _call_api(xml)
                except Exception as exc:
                    print(f"  {beschreibung:48} FEHLER {type(exc).__name__}: {exc}")
                    continue
                print(f"  {beschreibung:48} ({len(wert)} Zeichen)  {befund(root)}")
                gemessen += 1

    if was in ("alle", "id"):
        print("\n=== Nummernsuche, Runde 2: andere Query-Elemente ===")
        print("`Id` findet nichts; die Doku sagt, konkrete Requests koennen")
        print("`AbstractDefinedFieldsQuery` erweitern, nennt die Felder aber nicht.\n")
        erste = await _call_api(_build_trademark_search("<Any>Zürich*</Any>", 3))
        result = next(el for el in erste.iter() if _local(el.tag) == "Result")
        saetze = [kind for kind in result if (kind.get("role") or "") == "item"]
        if saetze:

            def feld(name: str) -> str:
                return next(
                    (
                        (el.text or "").strip()
                        for el in saetze[0].iter()
                        if _local(el.tag) == name and (el.text or "").strip()
                    ),
                    "",
                )

            anmelde, register = feld("ApplicationNumberText"), feld("RegistrationNumber")
            formen = []
            if anmelde:
                formen += [
                    ("Any mit ApplicationNumberText", f"<Any>{_esc(anmelde)}</Any>"),
                    ("ApplicationNumber-Element", f"<ApplicationNumber>{_esc(anmelde)}</ApplicationNumber>"),
                    (
                        "ApplicationNumberText-Element",
                        f"<ApplicationNumberText>{_esc(anmelde)}</ApplicationNumberText>",
                    ),
                ]
            if register:
                formen += [
                    ("Any mit RegistrationNumber", f"<Any>{_esc(register)}</Any>"),
                    ("RegistrationNumber-Element", f"<RegistrationNumber>{_esc(register)}</RegistrationNumber>"),
                ]
            for beschreibung, query in formen:
                try:
                    root = await _call_api(_build_trademark_search(query, 3))
                except Exception as exc:
                    print(f"  {beschreibung:38} FEHLER {type(exc).__name__}: {exc}")
                    continue
                print(f"  {beschreibung:38} {befund(root)}")
                gemessen += 1

    if was in ("alle", "pagination"):
        print("\n=== Pagination: Continuation als Action in der Folgeanfrage ===")
        erste = await _call_api(_build_trademark_search("<Any>Zürich*</Any>", 3))
        cont = next((el for el in erste.iter() if _local(el.tag) == "Continuation"), None)
        if cont is None:
            print("Keine Continuation in der ersten Antwort — Messung entfaellt", file=sys.stderr)
        else:

            def nummern(el: ET.Element) -> list[str]:
                return sorted(
                    (e.text or "").strip()
                    for e in el.iter()
                    if _local(e.tag) == "ApplicationNumberText" and (e.text or "").strip()
                )

            token = (cont.text or "").strip()
            name = cont.get("name") or "NextPage"
            # Genau wie die Doku es zeigt: das Continuation-Element als Kind
            # der naechsten ApiRequest, an der Stelle, an der sonst `Action`
            # steht.
            folge = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<ApiRequest xmlns="{NS_CORE}">\n'
                f'  <Continuation name="{_esc(name)}">{_esc(token)}</Continuation>\n'
                "</ApiRequest>"
            )
            try:
                zweite = await _call_api(folge)
            except Exception as exc:
                print(f"  Continuation-als-Action: FEHLER {type(exc).__name__}: {exc}")
            else:
                a, b = nummern(erste), nummern(zweite)
                gleich = bool(a) and a == b
                print(f"  Continuation-als-Action  {befund(zweite)}")
                print(f"  Seite 2 traegt {'DIESELBEN' if gleich else 'andere'} Saetze wie Seite 1")
                gemessen += 1

            # Kontrolle: der heutige Weg, damit die Nulllinie in derselben
            # Messung steht und nicht aus dem Gedaechtnis kommt.
            try:
                alt = await _call_api(_build_trademark_search("<Any>Zürich*</Any>", 3, token))
            except Exception as exc:
                print(f"  KONTROLLE Page-token: FEHLER {type(exc).__name__}: {exc}")
            else:
                a, b = nummern(erste), nummern(alt)
                gleich = bool(a) and a == b
                print(f"  KONTROLLE <Page token=...>  {befund(alt)}")
                print(f"  Seite 2 traegt {'DIESELBEN' if gleich else 'andere'} Saetze wie Seite 1")
                gemessen += 1

    if was in ("alle", "publikation"):
        print("\n=== Publikationssuche, Runde 2: der Rumpf ===")
        print("Die Fehlermeldungen unterscheiden sich: unbekannte Namen geben")
        print("«unsupported action type», `PatentPublicationSearch` dagegen")
        print("«could not parse the action». Der Name stimmt also, der Rumpf nicht.\n")
        for beschreibung, xml in publikations_rumpfe(NS_CORE, NS_COMMON, NS_PAT):
            try:
                root = await _call_api(xml)
            except Exception as exc:
                print(f"  {beschreibung:34} FEHLER {type(exc).__name__}: {exc}")
                continue
            print(f"  {beschreibung:34} {befund(root)}")
            gemessen += 1

        print("\n=== Publikationssuche: welcher Action-Typ wird geparst? ===")
        for action in PUBLIKATION_ACTIONS:
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<ApiRequest xmlns="{NS_CORE}" xmlns:pat="{NS_PAT}">\n'
                f'  <Action type="{action}">\n'
                f'    <pat:{action}Request xmlns="{NS_COMMON}">\n'
                '      <Representation details="Maximal"/>\n'
                '      <Page size="3"/>\n'
                "      <Query><Any>Roche*</Any></Query>\n"
                "    </pat:" + action + "Request>\n"
                "  </Action>\n"
                "</ApiRequest>"
            )
            try:
                root = await _call_api(xml)
            except Exception as exc:
                print(f"  {action:28} FEHLER {type(exc).__name__}: {exc}")
                continue
            print(f"  {action:28} {befund(root)}")
            gemessen += 1

    if srv._client is not None:
        await srv._client.aclose()
        srv._client = None

    print(f"\n{gemessen} Form(en) gemessen.")
    return 0 if gemessen else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="probe_request_forms")
    ap.add_argument("--was", choices=["alle", "id", "pagination", "publikation"], default="alle")
    args = ap.parse_args(argv)

    if not os.getenv("IGE_USERNAME") or not os.getenv("IGE_PASSWORD"):
        print("IGE_USERNAME und IGE_PASSWORD muessen gesetzt sein.", file=sys.stderr)
        return 1
    return asyncio.run(_messen(args.was))


if __name__ == "__main__":
    raise SystemExit(main())
