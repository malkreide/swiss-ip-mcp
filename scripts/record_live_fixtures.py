#!/usr/bin/env python3
"""Echte Antworten von swissreg.ch aufzeichnen — Struktur echt, Texte synthetisch.

WARUM
-----
`PROVENANCE.md` fuehrte die Antwort-Payloads bis zum 4.10.2026 als NICHT
AUFGEZEICHNET: Es gab keine Zugangsdaten. Die Folge stand im Code. Die
handgeschriebenen Fixtures nannten die Satzelemente `Item` und den Zaehler
`TotalCount`, der Parser suchte genau das, und beide irrten gleich — 171 gruene
Unit-Tests, waehrend jedes Suchwerkzeug in Wahrheit null Treffer lieferte
(Messung: Laeufe 37198882345 und 37198983962).

Ein Fixture, das aus demselben Kopf stammt wie der Parser, kann diesen Fehler
nicht finden. Also wird aufgezeichnet.

WAS AUFGEZEICHNET WIRD — UND WAS ERSETZT
----------------------------------------
Echt bleibt alles, woran der Parser arbeitet:

  - Elementnamen, Namespaces, Verschachtelung, Reihenfolge, Anzahl
  - Attributnamen und ihre Werte, bis auf die unten genannten
  - die Zaehler in `Meta` (`TotalItemCount`, `ItemCount`, `ItemCountOffset`) —
    sie muessen zur Satzzahl des Fixtures passen, sonst ist es in sich
    widersprueplich und die Tests pruefen eine Erfindung

Ersetzt wird der Inhalt: jeder uebrige Textknoten durch einen synthetischen
Wert derselben Zeichenklasse und Laenge (Ziffern bleiben Ziffern, Datumsangaben
bleiben gueltige Datumsangaben), der Continuation-Token durch einen
gleichlangen Platzhalter, und die Laufkennungen `requestUuid`, `timestamp`,
`uuid` am Wurzelelement.

DAS IST EINE EINSCHRAENKUNG, UND SIE GEHOERT BENANNT: Diese Fixtures belegen
die **Form** der Antwort, nicht ihren Inhalt. Ein Test darf aus ihnen ableiten,
dass drei Saetze gefunden werden und wie die Felder heissen — nicht, dass eine
bestimmte Marke so heisst. `tests/fixtures/live/RECORDING.md` haelt das samt
Datum fest, damit in zwei Jahren niemand sie fuer eine woertliche Aufzeichnung
nimmt.

Registerinhalte sind oeffentlich, unterliegen aber den IGE-Nutzungsbedingungen.
Fuer die Frage, die diese Fixtures beantworten, braucht sie niemand.

AUFRUF
------
Braucht `IGE_USERNAME` und `IGE_PASSWORD`; laeuft im Workflow
`shape-probe.yml` mit `mode: record`.

    python scripts/record_live_fixtures.py --out tests/fixtures/live
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

# Textknoten, deren Wert echt bleibt: die Zaehler, die zur Satzzahl passen
# muessen, und die Fehlermeldungen der Quelle. Letztere beziehen sich auf die
# eigene Anfrage — sie koennen keine fremden Registerinhalte tragen, und ohne
# ihren Wortlaut ist ein `FAIL_PARSE` nicht zu beheben. Am 4.10.2026 stand in
# `patent-publication-search.xml` genau das: ein anonymisierter Fehler, der
# nichts erklaerte.
KEEP_TEXT_TAGS = frozenset({"TotalItemCount", "ItemCount", "ItemCountOffset", "LogEntry"})

# Attribute am Wurzelelement, die einen einzelnen Lauf identifizieren.
SCRUB_ATTRS = frozenset({"requestUuid", "timestamp", "uuid"})

# Elemente, deren Text ein opaker Server-Token ist.
TOKEN_TAGS = frozenset({"Continuation"})

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})$")
BASIS = date(2020, 1, 1)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _synth(text: str, n: int) -> str:
    """Ein synthetischer Wert derselben Zeichenklasse und Laenge wie `text`.

    `n` macht es deterministisch und ueber die Datei hinweg verschieden, damit
    ein Test nicht versehentlich zwei Felder fuer gleich haelt, die es in der
    Antwort nicht sind.

    Nie gleich der Eingabe: Bei kurzen Werten — ein einstelliger Statuscode,
    ein Zweibuchstaben-Land — trifft der synthetische Wert den echten sonst
    irgendwann, und dann steht der Originalinhalt im Fixture. Gemessen am
    4.10.2026 an einem Lauf mit fuenfzehn einstelligen Codes: einmal.
    """
    for versuch in range(16):
        wert = _synth_einmal(text, n + versuch * 7919)
        if wert != text:
            return wert
    # Praktisch unerreichbar; lieber sichtbar scheitern als still durchlassen.
    raise ValueError(f"kein synthetischer Wert fuer {len(text)} Zeichen gefunden")


def _synth_einmal(text: str, n: int) -> str:
    if ISO_DATETIME.match(text):
        tag = (BASIS + timedelta(days=n % 3650)).isoformat()
        return f"{tag}T00:00:00.000000Z"[: len(text)].ljust(len(text), "0")
    if ISO_DATE.match(text):
        return (BASIS + timedelta(days=n % 3650)).isoformat()
    if text.isdigit():
        # Gleiche Laenge, keine fuehrende Null verlieren.
        return str(n % (10 ** len(text))).zfill(len(text))
    if re.fullmatch(r"[A-Za-z]{1,3}", text):
        # Codes wie `CH`, `de` bleiben Codes derselben Laenge. Nicht konstant
        # «X»: Bei einem einbuchstabigen Code gaebe es dann genau einen
        # moeglichen Wert, und fuer die Eingabe «X» keinen abweichenden.
        alphabet = "ABCDEFGHJKLMNPQRSTVWXYZ"
        return "".join(alphabet[(n + i) % len(alphabet)] for i in range(len(text)))
    # Alles uebrige: Buchstaben derselben Laenge, damit Laengen vergleichbar
    # bleiben — die stehen ohnehin schon im Strukturbericht der Sonde.
    kern = f"MUSTER{n}"
    if len(kern) >= len(text):
        return kern[: len(text)]
    return (kern + "X" * len(text))[: len(text)]


def anonymise(root: ET.Element) -> ET.Element:
    """Inhalte ersetzen, Form unberuehrt lassen. Arbeitet auf `root` selbst."""
    zaehler = 0
    for attr in list(root.attrib):
        if _local(attr) in SCRUB_ATTRS:
            root.set(attr, f"anonymisiert-{_local(attr)}")
    for el in root.iter():
        name = _local(el.tag)
        text = (el.text or "").strip()
        if not text:
            continue
        if name in KEEP_TEXT_TAGS:
            continue
        zaehler += 1
        if name in TOKEN_TAGS:
            el.text = ("CONTINUATION-TOKEN-ANONYMISIERT-" * 100)[: len(text)]
        else:
            el.text = _synth(text, zaehler)
    return root


def _hohe_entropie(text: str) -> bool:
    """Ist `text` ein Freitextwert, der nirgends auftauchen darf?

    Ziffernfolgen, kurze Codes und Datumsangaben sind es nicht: Der
    Synthetisierer erzeugt Werte derselben Klasse, und die treffen irgendwo im
    Dokument zwangslaeufig einen echten Wert eines ANDEREN Feldes. Das ist kein
    Leck, sondern eine Kollision. Namen, Adressen, Markentexte und Tokens
    dagegen sind lang und unregelmaessig genug, dass eine Kollision
    ausgeschlossen ist — bei ihnen heisst ein Treffer: durchgerutscht.
    """
    if len(text) < 8:
        return False
    if text.isdigit():
        return False
    return not (ISO_DATE.match(text) or ISO_DATETIME.match(text))


def anonymisierung_pruefen(root: ET.Element, original: ET.Element) -> list[str]:
    """Was an der Anonymisierung nicht stimmt — leere Liste heisst: in Ordnung.

    Zwei Regeln, und die erste ist die eigentliche:

    1. **Kein Element behaelt seinen eigenen Text.** Das ist Anonymisierung,
       Element fuer Element geprueft.
    2. **Kein Freitextwert steht irgendwo im Ergebnis.** Fuer Namen, Adressen
       und Tokens, auch an anderer Stelle als im Original.

    Die erste Fassung dieser Pruefung kannte nur eine globale Variante von
    Regel 2 und wandte sie auf JEDEN Wert an. Am 4.10.2026 meldete sie deshalb
    14 «Ueberlebende», von denen 13 Kollisionen zwischen einem synthetischen
    Datum und dem echten Datum eines anderen Feldes waren — und der Rekorder
    liess drei von vier Aufzeichnungen weg (Lauf 37201418733). Eine Bremse, die
    bei jeder Fahrt greift, ist keine Bremse.
    """
    probleme = []

    # Regel 1: paarweise durch beide Baeume. Sie sind strukturgleich, weil
    # `anonymise` nur Texte und Attributwerte anfasst.
    for alt, neu in zip(original.iter(), root.iter(), strict=True):
        text = (alt.text or "").strip()
        if not text or _local(alt.tag) in KEEP_TEXT_TAGS:
            continue
        if (neu.text or "").strip() == text:
            probleme.append(f"{_local(alt.tag)}: Text unveraendert")

    # Regel 2: Freitext darf nirgends mehr auftauchen.
    vorhanden = {(el.text or "").strip() for el in root.iter()}
    vorhanden |= {wert for el in root.iter() for wert in el.attrib.values()}
    for el in original.iter():
        text = (el.text or "").strip()
        if not text or _local(el.tag) in KEEP_TEXT_TAGS:
            continue
        if _hohe_entropie(text) and text in vorhanden:
            probleme.append(f"{_local(el.tag)}: Freitext steht noch im Ergebnis")
    return probleme


async def _folgeabfrage(name: str, build, out: Path, vergleich: ET.Element | None = None) -> list[str]:
    """Eine Folgeabfrage fahren, pruefen, schreiben. Gibt `[name]` oder `[]`.

    `vergleich` ist die erste Seite: Traegt die zweite dieselben Nummern, hat
    der Token nicht gewirkt, und die Pagination ist eine Attrappe. Das wird
    gemeldet, bevor irgendein Test darauf baut.
    """
    from swiss_ip_mcp.server import _call_api, _local

    try:
        root = await _call_api(build())
    except Exception as exc:
        print(f"{name}: FEHLGESCHLAGEN {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    def nummern(el: ET.Element) -> list[str]:
        return sorted(
            (e.text or "").strip()
            for e in el.iter()
            if _local(e.tag) == "ApplicationNumberText" and (e.text or "").strip()
        )

    if vergleich is not None:
        a, b = nummern(vergleich), nummern(root)
        if a and a == b:
            print(f"{name}: BEFUND — Seite 2 traegt dieselben Saetze wie Seite 1", file=sys.stderr)
        elif a and b:
            print(f"{name}: Seite 2 traegt andere Saetze als Seite 1 ({len(b)} Stueck)")
        else:
            print(f"{name}: Seitenvergleich nicht moeglich (a={len(a)}, b={len(b)})", file=sys.stderr)

    original = ET.fromstring(ET.tostring(root, encoding="unicode"))
    anonymise(root)
    probleme = anonymisierung_pruefen(root, original)
    if probleme:
        print(
            f"{name}: NICHT GESCHRIEBEN — {len(probleme)} Beanstandung(en): " + "; ".join(sorted(set(probleme))[:5]),
            file=sys.stderr,
        )
        return []
    ziel = out / f"{name}.xml"
    ziel.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    print(f"{name}: {ziel} ({ziel.stat().st_size} Bytes)")
    return [name]


async def _record(out: Path) -> int:
    import swiss_ip_mcp.server as srv
    from swiss_ip_mcp.server import (
        _build_patent_pub_search,
        _build_patent_search,
        _build_spc_search,
        _build_trademark_search,
        _call_api,
        _esc,
        _local,
        _quota_request,
    )

    def any_q(term: str) -> str:
        return f"<Any>{_esc(term)}</Any>"

    # Dieselben Abfragen wie die Live-Tests und die Sonde, plus die
    # Abfrageformen, die noch keine Aufzeichnung hatten: die Suche nach Nummer
    # (`<Id>`), die Publikationssuche (eigener Action-Typ) und die zweite
    # Seite. Ohne sie waere «alle Werkzeuge geprueft» eine Behauptung.
    auftraege = [
        ("trademark-search", lambda: _build_trademark_search(any_q("Zürich*"), 3)),
        ("patent-search", lambda: _build_patent_search(any_q("Roche*"), 3)),
        ("spc-search", lambda: _build_spc_search(any_q("Novartis*"), 3)),
        ("patent-publication-search", lambda: _build_patent_pub_search(any_q("Roche*"), 3)),
        ("quota", _quota_request),
    ]

    out.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for name, build in auftraege:
        try:
            root = await _call_api(build())
        except Exception as exc:
            print(f"{name}: FEHLGESCHLAGEN {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        original = ET.fromstring(ET.tostring(root, encoding="unicode"))
        anonymise(root)
        rest = anonymisierung_pruefen(root, original)
        if rest:
            # Nicht schreiben, was nicht anonym ist. Lieber kein Fixture als
            # eines, das Registerinhalte traegt.
            print(
                f"{name}: NICHT GESCHRIEBEN — {len(rest)} Originaltext(e) ueberlebten die Anonymisierung",
                file=sys.stderr,
            )
            continue
        ziel = out / f"{name}.xml"
        ziel.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        print(f"{name}: {ziel} ({ziel.stat().st_size} Bytes)")
        geschrieben.append(name)

    # Zwei Formen lassen sich nicht blind anfragen: Die Nummernsuche braucht
    # eine echte Nummer, die zweite Seite einen echten Token. Beide werden aus
    # einer frischen ersten Antwort gezogen und verlassen den Runner nur
    # anonymisiert.
    try:
        erste = await _call_api(_build_trademark_search(any_q("Zürich*"), 3))
    except Exception as exc:
        print(f"Folgeabfragen entfallen: {type(exc).__name__}: {exc}", file=sys.stderr)
        erste = None

    if erste is not None:
        nummern = [
            (el.text or "").strip()
            for el in erste.iter()
            if _local(el.tag) == "ApplicationNumberText" and (el.text or "").strip()
        ]
        if nummern:
            geschrieben += await _folgeabfrage(
                "trademark-by-number",
                lambda: _build_trademark_search(f"<Id>{_esc(nummern[0])}</Id>", 3),
                out,
            )
        else:
            print("keine ApplicationNumberText gefunden — Nummernsuche entfaellt", file=sys.stderr)

        token = next(
            (
                (el.text or "").strip()
                for el in erste.iter()
                if _local(el.tag) == "Continuation" and (el.text or "").strip()
            ),
            "",
        )
        if token:
            namen = await _folgeabfrage(
                "trademark-search-seite2",
                lambda: _build_trademark_search(any_q("Zürich*"), 3, token),
                out,
                vergleich=erste,
            )
            geschrieben += namen
        else:
            print("kein Continuation-Token gefunden — Seite 2 entfaellt", file=sys.stderr)

    if srv._client is not None:
        await srv._client.aclose()
        srv._client = None

    if not geschrieben:
        print("Keine Aufzeichnung zustande gekommen.", file=sys.stderr)
        return 1

    heute = date.today().isoformat()
    (out / "RECORDING.md").write_text(
        "\n".join(
            [
                "# Aufgezeichnete Antworten von swissreg.ch (IGE/IPI)",
                "",
                f"Aufgenommen am **{heute}** mit `scripts/record_live_fixtures.py`",
                "aus den Abfragen der Live-Suite (`page_size=3`, `<Any>`-Wrapper):",
                "`Zürich*` (Marken), `Roche*` (Patente), `Novartis*` (SPC), sowie das",
                "Kontingent.",
                "",
                "## Was hier echt ist",
                "",
                "Elementnamen, Namespaces, Verschachtelung, Reihenfolge und Anzahl;",
                "Attributnamen und -werte; die Zaehler in `Meta` (`TotalItemCount`,",
                "`ItemCount`, `ItemCountOffset`).",
                "",
                "## Was ersetzt ist",
                "",
                "Jeder uebrige Textknoten durch einen synthetischen Wert derselben",
                "Zeichenklasse und Laenge, der Continuation-Token durch einen",
                "gleichlangen Platzhalter, und `requestUuid`/`timestamp`/`uuid` am",
                "Wurzelelement.",
                "",
                "**Diese Dateien belegen die Form der Antwort, nicht ihren Inhalt.**",
                "Ein Test darf aus ihnen ableiten, wie die Felder heissen und wie viele",
                "Saetze eine Seite traegt — nicht, dass ein bestimmter Datensatz so",
                "aussieht. Wer sie fuer eine woertliche Aufzeichnung nimmt, zieht",
                "Schluesse, die sie nicht tragen.",
                "",
                f"Geschrieben: {', '.join(sorted(geschrieben))}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"\n{len(geschrieben)} Antwort(en) aufgezeichnet.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="record_live_fixtures")
    ap.add_argument("--out", type=Path, default=Path("tests/fixtures/live"))
    args = ap.parse_args(argv)

    if not os.getenv("IGE_USERNAME") or not os.getenv("IGE_PASSWORD"):
        print(
            "IGE_USERNAME und IGE_PASSWORD muessen gesetzt sein — ohne sie gibt es nichts aufzuzeichnen.",
            file=sys.stderr,
        )
        return 1
    return asyncio.run(_record(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
