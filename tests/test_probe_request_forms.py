#!/usr/bin/env python3
"""Tests fuer scripts/probe_request_forms.py — die Sonde ohne Netz durchgehen.

WARUM ES DIESE DATEI GIBT. Die Sonde lief am 4.10.2026 zweimal in die CI und
scheiterte beim zweiten Mal an einem eigenen Fehler: einer Liste von Tupeln
verschiedener Laenge (`ValueError: too many values to unpack`, Lauf
37204275286). Das kostete zwei Minuten Wartezeit und einen Lauf mit
Zugangsdaten, um etwas zu finden, das jeder Aufruf ohne Netz gezeigt haette.

Eine Messsonde ist Code wie jeder andere. Was sich ohne Quelle pruefen laesst —
dass die gebauten Anfragen wohlgeformt sind und die Kandidatenlisten die
erwartete Form haben — wird hier geprueft.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import probe_request_forms as prf  # noqa: E402


def ohne_deklaration(xml: str) -> str:
    return xml.split("?>", 1)[1] if "?>" in xml else xml


class TestPublikationsRumpfe(unittest.TestCase):
    def setUp(self) -> None:
        self.rumpfe = prf.publikations_rumpfe("urn:core", "urn:common", "urn:pat")

    def test_jede_variante_ist_wohlgeformtes_xml(self):
        for beschreibung, xml in self.rumpfe:
            with self.subTest(beschreibung):
                ET.fromstring(ohne_deklaration(xml))

    def test_jede_variante_ist_ein_paar(self):
        # Der Fehler, der in die CI durchging: Tupel verschiedener Laenge.
        for eintrag in self.rumpfe:
            self.assertEqual(len(eintrag), 2, eintrag)

    def test_oeffnendes_und_schliessendes_element_passen(self):
        # Mit danebengelegtem `praefix` liefen die beiden auseinander; jetzt
        # stammen sie aus derselben Variablen. Der Test haelt das fest.
        for beschreibung, xml in self.rumpfe:
            with self.subTest(beschreibung):
                baum = ET.fromstring(ohne_deklaration(xml))
                action = list(baum)[0]
                self.assertEqual(len(list(action)), 1, "genau ein Request-Element je Action")

    def test_action_typ_bleibt_der_von_der_quelle_erkannte(self):
        # `PatentPublicationSearch` ist bekannt — die Quelle sagt
        # «could not parse the action», nicht «unsupported action type».
        # Variiert wird der Rumpf, nicht der Name.
        for beschreibung, xml in self.rumpfe:
            with self.subTest(beschreibung):
                self.assertIn('type="PatentPublicationSearch"', xml)

    def test_varianten_unterscheiden_sich_wirklich(self):
        xmls = [xml for _, xml in self.rumpfe]
        self.assertEqual(len(set(xmls)), len(xmls), "zwei Varianten sind identisch")


class TestIdKandidaten(unittest.TestCase):
    SATZ = ET.fromstring(
        "<Data><Trademark>"
        "<ApplicationNumber><ApplicationNumberText>0012345678</ApplicationNumberText></ApplicationNumber>"
        "<RegistrationNumber>000042</RegistrationNumber>"
        "<RegistrationOfficeCode>CH</RegistrationOfficeCode>"
        "</Trademark></Data>"
    )

    def test_leitet_alle_formen_aus_dem_satz_ab(self):
        kandidaten = prf.id_kandidaten(self.SATZ)
        werte = {wert for _, wert in kandidaten}
        # Nichts erfunden: Jeder Wert enthaelt eine Zahl aus dem Satz.
        for wert in werte:
            self.assertTrue(
                "0012345678" in wert or "12345678" in wert or "000042" in wert or "42" in wert,
                f"{wert!r} stammt nicht aus dem Satz",
            )

    def test_fuehrende_nullen_werden_wirklich_entfernt(self):
        kandidaten = dict((b, w) for b, w in prf.id_kandidaten(self.SATZ))
        self.assertEqual(kandidaten["ApplicationNumberText ohne fuehrende Nullen"], "12345678")
        self.assertEqual(kandidaten["RegistrationNumber ohne fuehrende Nullen"], "42")

    def test_ohne_nummern_keine_kandidaten(self):
        # Ein Satz ohne Nummernfelder darf nicht zu erfundenen Formen fuehren.
        leer = ET.fromstring("<Data><Trademark/></Data>")
        self.assertEqual(prf.id_kandidaten(leer), [])

    def test_beschreibungen_sind_eindeutig(self):
        beschreibungen = [b for b, _ in prf.id_kandidaten(self.SATZ)]
        self.assertEqual(len(set(beschreibungen)), len(beschreibungen))


class TestBefund(unittest.TestCase):
    def test_nennt_success_zaehler_und_saetze(self):
        root = ET.fromstring(
            '<ApiResponse><Result success="true">'
            '<Data role="item"/><Data role="item"/>'
            "<Meta><TotalItemCount>115</TotalItemCount></Meta>"
            "</Result></ApiResponse>"
        )
        zeile = prf.befund(root)
        self.assertIn("success=true", zeile)
        self.assertIn("total=115", zeile)
        self.assertIn("saetze=2", zeile)

    def test_nennt_den_log_grund_im_wortlaut(self):
        root = ET.fromstring(
            '<ApiResponse><Result success="false"><Log>'
            '<LogEntry level="ERROR" code="FAIL_PARSE">could not parse the action X</LogEntry>'
            "</Log></Result></ApiResponse>"
        )
        zeile = prf.befund(root)
        self.assertIn("success=false", zeile)
        self.assertIn("FAIL_PARSE", zeile)
        self.assertIn("could not parse the action X", zeile)

    def test_zaehlt_nur_role_item(self):
        # Die Kontingent-Antwort traegt `role="quota"` und ist kein Satz.
        root = ET.fromstring('<ApiResponse><Result success="true"><Data role="quota"/></Result></ApiResponse>')
        self.assertIn("saetze=0", prf.befund(root))


if __name__ == "__main__":
    unittest.main()
