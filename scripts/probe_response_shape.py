#!/usr/bin/env python3
"""Welche Form hat eine echte Antwort von swissreg.ch — gemessen, nicht geraten.

WARUM DAS SKRIPT EXISTIERT
--------------------------
`_parse_result_page` zaehlt Elemente mit dem lokalen Namen `Item` und liest
`Meta/TotalCount`. Ob die Quelle ihre Felder so nennt, war bis zum 4.10.2026
unbelegt: `PROVENANCE.md` fuehrt die Antwort-Payloads als NICHT AUFGEZEICHNET,
weil es keine Zugangsdaten gab.

Im ersten Lauf mit Zugangsdaten (37197766646) kam `test_live_trademark_search`
auf `count == 0` fuer `Zürich*`. Zwei Erklaerungen passen dazu, und die
Fehlermeldung unterscheidet sie nicht:

  - Die Abfrage hat wirklich keine Treffer.
  - Der Parser sucht den falschen Namen.

Beides laesst sich nur an der Antwort selbst entscheiden. Also wird sie
abgefragt und ihre Form berichtet.

WAS DAS SKRIPT AUSGIBT — UND WAS NICHT
--------------------------------------
Berichtet werden Struktur und nichts weiter: je Elementpfad (ohne Namespace)
die Anzahl, die Attributnamen und ob das Element Text traegt, dazu dessen
Laenge in Zeichen.

Die Textinhalte selbst bleiben draussen. Es sind oeffentliche Registerdaten,
aber sie unterliegen den IGE-Nutzungsbedingungen, und fuer die Frage, die hier
beantwortet werden soll, braucht niemand sie: Dass ein `MarkName` existiert,
sagt alles; wie die Marke heisst, nichts.

Die einzige Ausnahme ist `TotalCount`. Dessen Wert IST die Antwort auf die
Frage — steht dort eine Zahl groesser null, waehrend der Parser keine Items
findet, ist die Sache entschieden. Zahlen sind keine Registerinhalte.

Ausgabe ausserdem: was `_parse_result_page` aus derselben Antwort gemacht hat.
Nebeneinander ist die Luecke sichtbar, statt erschlossen.

AUFRUF
------
Braucht `IGE_USERNAME` und `IGE_PASSWORD` in der Umgebung — also entweder
lokal mit eigenen Zugangsdaten oder im Workflow `shape-probe.yml`.

    python scripts/probe_response_shape.py
    python scripts/probe_response_shape.py --only trademark

Der Exit-Code ist 0, solange ueberhaupt gemessen werden konnte; ueber richtig
oder falsch entscheidet der Mensch, der die Ausgabe liest. Nur wenn keine
einzige Abfrage durchkam, endet es mit 1 — dann wurde nichts gemessen, und ein
gruener Haken daraufhin waere derselbe Fehler wie der uebersprungene Testlauf.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter

# Werte, deren Text berichtet werden darf: Zaehler, keine Registerinhalte.
NUMERIC_TAGS = frozenset({"TotalCount"})


def describe_shape(root: ET.Element) -> list[str]:
    """Die Form eines Antwortbaums als Zeilen — Pfade, Attribute, Textlaengen.

    Kein Textinhalt, mit Ausnahme von `NUMERIC_TAGS`. Die Pfade sind
    namespace-frei, weil der Parser des Servers auch namespace-frei sucht: Die
    Frage ist, wie die Elemente *heissen*, nicht in welchem Namensraum.
    """
    from swiss_ip_mcp.server import _local

    paths: Counter[str] = Counter()
    attrs: dict[str, set[str]] = {}
    text_lens: dict[str, list[int]] = {}
    values: dict[str, set[str]] = {}

    def walk(el: ET.Element, prefix: str) -> None:
        path = f"{prefix}/{_local(el.tag)}"
        paths[path] += 1
        attrs.setdefault(path, set()).update(el.attrib.keys())
        text = (el.text or "").strip()
        if text:
            text_lens.setdefault(path, []).append(len(text))
            if _local(el.tag) in NUMERIC_TAGS:
                values.setdefault(path, set()).add(text)
        for child in el:
            walk(child, path)

    walk(root, "")

    lines = []
    for path in sorted(paths):
        parts = [f"{paths[path]:>4}×  {path}"]
        if attrs[path]:
            parts.append(f"attr: {','.join(sorted(attrs[path]))}")
        if path in text_lens:
            lens = text_lens[path]
            parts.append(f"text: {len(lens)}×, {min(lens)}–{max(lens)} Zeichen")
        if path in values:
            parts.append(f"wert: {','.join(sorted(values[path]))}")
        lines.append("  ".join(parts))
    return lines


async def _probe(name: str, build_body) -> tuple[str, list[str], str]:
    """Eine Abfrage fahren und (Name, Formzeilen, Parser-Urteil) zurueckgeben."""
    from swiss_ip_mcp.server import _call_api, _parse_result_page

    root = await _call_api(build_body())
    shape = describe_shape(root)
    try:
        env = _parse_result_page(root)
        verdict = f"count={env.count}  total={env.total!r}  match_type={env.match_type}"
    except Exception as exc:  # pragma: no cover - nur im Live-Lauf erreichbar
        verdict = f"_parse_result_page fiel: {type(exc).__name__}: {exc}"
    return name, shape, verdict


def _queries(only: str | None) -> list[tuple[str, object]]:
    from swiss_ip_mcp.server import (
        _build_patent_search,
        _build_spc_search,
        _build_trademark_search,
        _esc,
        _quota_request,
    )

    # Dieselben Abfragen wie die Live-Tests, damit die Messung deren Befund
    # erklaert und nicht einen anderen Fall beschreibt: gleicher `<Any>`-Wrapper
    # wie in den Tools, gleiche Suchbegriffe, gleiches `page_size=3`. Ein
    # selbstgebauter `<MarkName>`-Filter waere eine andere Abfrage und koennte
    # den Befund weder bestaetigen noch widerlegen.
    def any_q(term: str) -> str:
        return f"<Any>{_esc(term)}</Any>"

    all_q: list[tuple[str, object]] = [
        ("trademark Zürich*", lambda: _build_trademark_search(any_q("Zürich*"), 3)),
        ("patent Roche*", lambda: _build_patent_search(any_q("Roche*"), 3)),
        ("spc Novartis*", lambda: _build_spc_search(any_q("Novartis*"), 3)),
        ("quota", _quota_request),
    ]
    if only:
        return [q for q in all_q if q[0].split()[0] == only]
    return all_q


async def main_async(only: str | None) -> int:
    import swiss_ip_mcp.server as srv

    queries = _queries(only)
    if not queries:
        print(f"Keine Abfrage passt zu --only {only!r}", file=sys.stderr)
        return 2

    gemessen = 0
    for name, build in queries:
        print(f"\n{'=' * 72}\n{name}\n{'=' * 72}")
        try:
            _, shape, verdict = await _probe(name, build)
        except Exception as exc:
            # Weitermachen: Eine Abfrage, die scheitert, sagt nichts ueber die
            # naechste — und genau diese Vermischung soll die Messung aufloesen.
            print(f"FEHLGESCHLAGEN: {type(exc).__name__}: {exc}")
            continue
        gemessen += 1
        print("\n-- Form der Antwort --")
        for line in shape:
            print(line)
        print("\n-- was _parse_result_page daraus macht --")
        print(verdict)

    if srv._client is not None:
        await srv._client.aclose()
        srv._client = None

    print(f"\n{gemessen} von {len(queries)} Abfrage(n) gemessen.")
    # Keine Messung heisst kein Befund — dann ist rot die richtige Antwort.
    return 0 if gemessen else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="probe_response_shape")
    ap.add_argument(
        "--only",
        choices=["trademark", "patent", "spc", "quota"],
        default=None,
        help="nur eine der vier Abfragen fahren",
    )
    args = ap.parse_args(argv)

    if not os.getenv("IGE_USERNAME") or not os.getenv("IGE_PASSWORD"):
        print(
            "IGE_USERNAME und IGE_PASSWORD muessen gesetzt sein — ohne sie gibt es keine Antwort zu messen.",
            file=sys.stderr,
        )
        return 1
    return asyncio.run(main_async(args.only))


if __name__ == "__main__":
    raise SystemExit(main())
