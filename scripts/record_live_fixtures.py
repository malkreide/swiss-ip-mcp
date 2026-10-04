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

# Textknoten, deren Wert echt bleibt: Zaehler, die zur Satzzahl passen muessen.
KEEP_TEXT_TAGS = frozenset({"TotalItemCount", "ItemCount", "ItemCountOffset"})

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
    """
    if ISO_DATETIME.match(text):
        tag = (BASIS + timedelta(days=n % 3650)).isoformat()
        return f"{tag}T00:00:00.000000Z"[: len(text)].ljust(len(text), "0")
    if ISO_DATE.match(text):
        return (BASIS + timedelta(days=n % 3650)).isoformat()
    if text.isdigit():
        # Gleiche Laenge, keine fuehrende Null verlieren.
        return str(n % (10 ** len(text))).zfill(len(text))
    if re.fullmatch(r"[A-Za-z]{1,3}", text):
        # Codes wie `CH`, `de`, `A1` bleiben Codes derselben Laenge.
        return ("X" * len(text))[: len(text)]
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


def restliche_klartexte(root: ET.Element, original: ET.Element) -> list[str]:
    """Welche Texte aus `original` stehen noch in `root`? Fuer die Gegenprobe."""
    verbleibend = []
    neu = {(el.text or "").strip() for el in root.iter()}
    for el in original.iter():
        text = (el.text or "").strip()
        if not text or _local(el.tag) in KEEP_TEXT_TAGS:
            continue
        if text in neu:
            verbleibend.append(text)
    return verbleibend


async def _record(out: Path) -> int:
    import swiss_ip_mcp.server as srv
    from swiss_ip_mcp.server import (
        _build_patent_search,
        _build_spc_search,
        _build_trademark_search,
        _call_api,
        _esc,
        _quota_request,
    )

    def any_q(term: str) -> str:
        return f"<Any>{_esc(term)}</Any>"

    # Dieselben Abfragen wie die Live-Tests und die Sonde.
    auftraege = [
        ("trademark-search", lambda: _build_trademark_search(any_q("Zürich*"), 3)),
        ("patent-search", lambda: _build_patent_search(any_q("Roche*"), 3)),
        ("spc-search", lambda: _build_spc_search(any_q("Novartis*"), 3)),
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
        rest = restliche_klartexte(root, original)
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
    print(f"\n{len(geschrieben)} von {len(auftraege)} Antwort(en) aufgezeichnet.")
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
