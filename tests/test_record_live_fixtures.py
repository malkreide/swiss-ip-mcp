#!/usr/bin/env python3
"""Tests fuer scripts/record_live_fixtures.py — Form behalten, Inhalt ersetzen.

Der Rekorder schreibt Dateien, die im Repo liegen und die Grundlage der
Parser-Tests sind. Zwei Dinge muessen deshalb zugesichert sein, und beide
gegenlaeufig:

  - Die Form bleibt unberuehrt. Wer sie mit anonymisiert, nimmt den Fixtures
    genau die Eigenschaft, fuer die sie aufgenommen wurden.
  - Vom Inhalt bleibt nichts stehen. Der Rekorder schreibt gar nicht, wenn
    doch — `restliche_klartexte` ist die Selbstkontrolle dafuer, und sie wird
    hier gegen einen Fall gehalten, in dem sie anschlagen muss.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import record_live_fixtures as rlf  # noqa: E402

ANTWORT = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0"
             requestUuid="11111111-2222-3333-4444-555555555555"
             timestamp="2026-10-04T11:29:20Z"
             uuid="99999999-8888-7777-6666-555555555555">
  <Result success="true">
    <Data role="trademark">
      <Trademark>
        <RegistrationNumber>812345</RegistrationNumber>
        <RegistrationDate>2019-03-14</RegistrationDate>
        <RegistrationOfficeCode>CH</RegistrationOfficeCode>
        <MarkRepresentation>
          <MarkReproduction>
            <WordMarkSpecification>
              <MarkSignificantVerbalElementText>ZUERITEST PRO</MarkSignificantVerbalElementText>
            </WordMarkSpecification>
          </MarkReproduction>
        </MarkRepresentation>
        <Version><VersionDateTime>2026-09-30T22:00:00.000000Z</VersionDateTime></Version>
      </Trademark>
    </Data>
    <Continuations>
      <Continuation name="next">OPAKER-TOKEN-AUS-DER-QUELLE-1234567890</Continuation>
    </Continuations>
    <Meta>
      <ItemCount>3</ItemCount>
      <ItemCountOffset>0</ItemCountOffset>
      <TotalItemCount>123456</TotalItemCount>
    </Meta>
  </Result>
</ApiResponse>"""

INHALTE = (
    "812345",
    "2019-03-14",
    "ZUERITEST PRO",
    "2026-09-30T22:00:00.000000Z",
    "OPAKER-TOKEN-AUS-DER-QUELLE-1234567890",
)


def pfade(root: ET.Element) -> list[str]:
    """Jeder Elementpfad mit Attributnamen und -werten — die Form."""
    out = []

    def walk(el: ET.Element, prefix: str) -> None:
        p = f"{prefix}/{el.tag}"
        attrs = ",".join(f"{k}={v}" for k, v in sorted(el.attrib.items()))
        out.append(f"{p}[{attrs}]")
        for kind in el:
            walk(kind, p)

    walk(root, "")
    return out


class TestAnonymise(unittest.TestCase):
    def setUp(self) -> None:
        self.original = ET.fromstring(ANTWORT)
        self.anonym = rlf.anonymise(ET.fromstring(ANTWORT))
        self.xml = ET.tostring(self.anonym, encoding="unicode")

    def test_form_bleibt_identisch(self):
        # Bis auf die Lauf-Attribute am Wurzelelement, die ersetzt werden.
        vorher = [p for p in pfade(self.original) if not p.endswith("]") or True]
        nachher = pfade(self.anonym)
        self.assertEqual(len(vorher), len(nachher))
        # Pfade ohne Attribute muessen Zeichen fuer Zeichen gleich sein.
        nur_pfad = lambda ps: [p.split("[")[0] for p in ps]  # noqa: E731
        self.assertEqual(nur_pfad(vorher), nur_pfad(nachher))

    def test_attributwerte_bleiben_bis_auf_laufkennungen(self):
        self.assertIn('success="true"', self.xml)
        self.assertIn('role="trademark"', self.xml)
        self.assertIn('name="next"', self.xml)
        for wert in (
            "11111111-2222-3333-4444-555555555555",
            "99999999-8888-7777-6666-555555555555",
            "2026-10-04T11:29:20Z",
        ):
            self.assertNotIn(wert, self.xml, f"{wert!r} ist eine Laufkennung")

    def test_meta_zaehler_bleiben_echt(self):
        # Sie muessen zur Satzzahl passen, sonst ist das Fixture in sich falsch.
        for tag in ("ItemCount", "ItemCountOffset", "TotalItemCount"):
            el = [e for e in self.anonym.iter() if rlf._local(e.tag) == tag][0]
            vorher = [e for e in self.original.iter() if rlf._local(e.tag) == tag][0]
            self.assertEqual(el.text, vorher.text, tag)

    def test_kein_inhalt_ueberlebt(self):
        for inhalt in INHALTE:
            self.assertNotIn(inhalt, self.xml, f"{inhalt!r} steht noch im Fixture")

    def test_zeichenklassen_bleiben_erhalten(self):
        def text(tag: str) -> str:
            return [e.text for e in self.anonym.iter() if rlf._local(e.tag) == tag][0]

        self.assertRegex(text("RegistrationNumber"), r"^\d{6}$")
        self.assertRegex(text("RegistrationDate"), r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(text("VersionDateTime"), r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(len(text("RegistrationOfficeCode")), 2)

    def test_token_behaelt_laenge(self):
        tok = [e for e in self.anonym.iter() if rlf._local(e.tag) == "Continuation"][0]
        original = [e for e in self.original.iter() if rlf._local(e.tag) == "Continuation"][0]
        self.assertEqual(len(tok.text or ""), len(original.text or ""))
        self.assertIn("ANONYMISIERT", tok.text or "")


class TestSelbstkontrolle(unittest.TestCase):
    """`restliche_klartexte` ist die Bremse des Rekorders — sie muss greifen."""

    def test_meldet_nichts_bei_sauberer_anonymisierung(self):
        original = ET.fromstring(ANTWORT)
        anonym = rlf.anonymise(ET.fromstring(ANTWORT))
        self.assertEqual(rlf.restliche_klartexte(anonym, original), [])

    def test_meldet_ueberlebenden_text(self):
        # Gegenprobe: ein Baum, der gar nicht anonymisiert wurde.
        original = ET.fromstring(ANTWORT)
        rest = rlf.restliche_klartexte(ET.fromstring(ANTWORT), original)
        self.assertIn("ZUERITEST PRO", rest)
        # Die Meta-Zaehler duerfen nicht als Fund gelten, sie bleiben absichtlich.
        self.assertNotIn("123456", rest)


class TestSynth(unittest.TestCase):
    def test_laenge_bleibt(self):
        for text in ("812345", "CH", "ZUERITEST PRO", "2019-03-14", "x" * 70):
            self.assertEqual(len(rlf._synth(text, 7)), len(text), repr(text))

    def test_deterministisch(self):
        self.assertEqual(rlf._synth("ZUERITEST", 3), rlf._synth("ZUERITEST", 3))

    def test_verschiedene_zaehler_verschiedene_werte(self):
        # Sonst halten Tests zwei Felder fuer gleich, die es nicht sind.
        a, b = rlf._synth("ZUERITEST PRO", 1), rlf._synth("ZUERITEST PRO", 2)
        self.assertNotEqual(a, b)

    def test_ziffern_bleiben_ziffern(self):
        self.assertTrue(rlf._synth("00812345", 5).isdigit())
        self.assertEqual(len(rlf._synth("00812345", 5)), 8)

    def test_datum_bleibt_gueltig(self):
        import datetime

        datetime.date.fromisoformat(rlf._synth("2019-03-14", 11))


if __name__ == "__main__":
    unittest.main()
