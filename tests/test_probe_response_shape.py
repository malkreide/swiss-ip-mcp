#!/usr/bin/env python3
"""Tests fuer scripts/probe_response_shape.py — Form berichten, Inhalt nicht.

Die Sonde laeuft mit echten Zugangsdaten gegen swissreg.ch, und ihre Ausgabe
landet in einem Workflow-Log, das jeder lesen kann, der das Repo lesen kann.
Was sie berichtet, ist deshalb eine Zusicherung und keine Geschmacksfrage: Es
sind oeffentliche Registerdaten, aber sie unterliegen den IGE-Nutzungsbedingungen,
und fuer die Frage, warum `_parse_result_page` null Items findet, braucht
niemand die Namen der Marken.

Der wichtigste Test ist deshalb `test_kein_registerinhalt_in_der_ausgabe`. Er
faellt, sobald jemand Textinhalte durchreicht oder `NUMERIC_TAGS` weiter
aufmacht als Zaehler.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import probe_response_shape as prs  # noqa: E402

# Nachgebaut nach der Form, die der Parser erwartet — mit Namespace, weil die
# echten Antworten einen tragen und die Sonde ihn abstreifen soll.
ANTWORT = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0">
  <Result>
    <Meta><TotalCount>42</TotalCount></Meta>
    <Item>
      <ApplicationNumber>P-756001</ApplicationNumber>
      <MarkName>ZUERITEST</MarkName>
    </Item>
    <Item>
      <ApplicationNumber>P-756002</ApplicationNumber>
      <MarkName>ZUERITEST PRO</MarkName>
    </Item>
    <Continuation><Page size="3" token="abc123"/></Continuation>
  </Result>
</ApiResponse>"""


ZEILE = re.compile(r"^\s*(\d+)×\s+(\S+)\s*(.*)$")


def zerlege(lines: list[str]) -> dict[str, tuple[int, str]]:
    """{Pfad: (Anzahl, Rest)} — der Pfad exakt, nicht per `endswith`.

    Die Zeilen haengen hinter den Pfad noch Attribute und Textlaengen; ein
    `endswith(pfad)` traf deshalb nur die Zeilen ohne Zusatz und war je nach
    Antwort still leer.
    """
    out = {}
    for ln in lines:
        m = ZEILE.match(ln)
        assert m, f"Zeile passt nicht ins Format: {ln!r}"
        out[m.group(2)] = (int(m.group(1)), m.group(3))
    return out


class TestDescribeShape(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = prs.describe_shape(ET.fromstring(ANTWORT))
        self.text = "\n".join(self.lines)
        self.pfade = zerlege(self.lines)

    def test_pfade_sind_namespace_frei(self):
        # Der Parser des Servers sucht namespace-frei; die Sonde muss dieselbe
        # Sicht zeigen, sonst beantwortet sie eine andere Frage.
        self.assertNotIn("urn:ige", self.text)
        self.assertNotIn("{", self.text)

    def test_zaehlt_wiederholte_elemente(self):
        anzahl, _ = self.pfade["/ApiResponse/Result/Item"]
        self.assertEqual(anzahl, 2)

    def test_nennt_attributnamen(self):
        _, rest = self.pfade["/ApiResponse/Result/Continuation/Page"]
        self.assertIn("attr: size,token", rest)

    def test_totalcount_wird_im_klartext_berichtet(self):
        # Dessen Wert IST die Frage: Steht dort eine Zahl groesser null und
        # findet der Parser trotzdem keine Items, ist die Sache entschieden.
        _, rest = self.pfade["/ApiResponse/Result/Meta/TotalCount"]
        self.assertIn("wert: 42", rest)

    def test_kein_registerinhalt_in_der_ausgabe(self):
        # Die eigentliche Zusicherung: Elementnamen ja, Inhalte nein.
        self.assertIn("MarkName", self.text)  # der Name des Feldes
        for inhalt in ("ZUERITEST", "ZUERITEST PRO", "P-756001", "P-756002", "abc123"):
            self.assertNotIn(inhalt, self.text, f"{inhalt!r} steht in der Ausgabe")

    def test_textlaenge_statt_text(self):
        _, rest = self.pfade["/ApiResponse/Result/Item/MarkName"]
        self.assertIn("text: 2×", rest)
        self.assertIn("9–13 Zeichen", rest)  # ZUERITEST, ZUERITEST PRO

    def test_leere_antwort_bleibt_messbar(self):
        # Der Fall, um den es geht: eine Antwort ohne Items. Die Sonde muss ihn
        # berichten koennen, statt an ihm zu scheitern — sonst bleibt genau die
        # Frage offen, fuer die sie geschrieben ist.
        leer = (
            '<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0">'
            "<Result><Meta><TotalCount>0</TotalCount></Meta></Result></ApiResponse>"
        )
        lines = prs.describe_shape(ET.fromstring(leer))
        text = "\n".join(lines)
        self.assertIn("wert: 0", text)
        self.assertNotIn("/Item", text)


class TestNumericAllowlist(unittest.TestCase):
    def test_nur_zaehler_duerfen_ihren_wert_zeigen(self):
        # Gegenprobe-Anker: Wer hier ein Inhaltsfeld eintraegt, laesst
        # Registerdaten ins Log. Die Liste bleibt klein und sichtbar.
        self.assertEqual(set(prs.NUMERIC_TAGS), {"TotalCount"})


if __name__ == "__main__":
    unittest.main()
