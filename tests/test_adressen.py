"""Ob die Adressen, der Realm und der Client stimmen — ohne Zugangsdaten.

Ohne Netz. Grundlage ist `tests/fixtures/adressen.json`, aufgezeichnet am
2026-08-08 von `scripts/record_fixtures.py`.

Das Ergebnis ist ein **Nullbefund**: Jede Adresse, die dieser Server baut, ist
die, die die Quelle fuehrt. Genau deshalb steht es hier — ein Nullbefund ohne
Aufzeichnung ist beim naechsten Durchgang keiner mehr.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from swiss_ip_mcp.server import API_ENDPOINT, CLIENT_ID, IDP_TOKEN_URL

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fix() -> dict:
    pfad = FIXTURES / "adressen.json"
    if not pfad.is_file():
        raise FileNotFoundError(
            f"Keine Fixture unter {pfad}. Neu aufzeichnen mit "
            "`python scripts/record_fixtures.py`."
        )
    return copy.deepcopy(json.loads(pfad.read_text(encoding="utf-8")))


class TestIdentityProvider:
    """Der Keycloak unterscheidet drei Faelle — und das ist der ganze Beleg."""

    def test_der_konfigurierte_client_meldet_nur_fehlende_zugangsdaten(self):
        g = _fix()["idp"]["gebaut"]
        assert g["url"] == IDP_TOKEN_URL
        assert g["error"] == "invalid_grant", (
            "`invalid_grant` heisst: Realm und Client existieren, nur die "
            f"Zugangsdaten fehlen. Gemessen wurde {g['error']!r}."
        )

    def test_ein_erfundener_realm_gibt_404(self):
        """Ohne diese Kontrolle belegt der Test darueber nicht, dass `egov` existiert."""
        k = _fix()["idp"]["kontrolle_erfundener_realm"]
        assert k["status"] == 404
        assert "Realm does not exist" in k["error"]

    def test_ein_erfundener_client_gibt_invalid_client(self):
        """Die zweite Kontrolle, und sie trennt eine andere Sache.

        Ohne sie liesse sich «der Client existiert» nicht von «irgendetwas an
        der Anfrage stimmt nicht» unterscheiden.
        """
        assert _fix()["idp"]["kontrolle_erfundener_client"]["error"] == "invalid_client"

    def test_der_realm_nennt_denselben_token_endpunkt(self):
        """Nicht abgeleitet, sondern von der Quelle deklariert."""
        assert _fix()["realm_deklariert_token_endpoint"] == IDP_TOKEN_URL


class TestSwissregApi:
    def test_die_api_unterscheidet_nicht_zwischen_echt_und_erfunden(self):
        """Der Grund, warum es den Umweg ueber die Doku braucht.

        Gebauter und frei erfundener Pfad antworten identisch. Ein Statuscode
        belegt dort also nichts — und aus genau dieser Lage wurde bei
        `epl.bag.admin.ch` in diesem Portfolio faelschlich «die Route
        existiert» geschlossen.

        Faengt die API an zu unterscheiden, ist das eine gute Nachricht und
        ein Anlass, neu zu messen — nicht, diesen Test anzupassen.
        """
        a = _fix()["api"]
        assert a["gebaut"]["status_ohne_token"] == a["kontrolle_erfundener_pfad"]["status_ohne_token"]

    def test_die_offizielle_doku_deklariert_jeden_wert(self):
        d = _fix()["doku_deklariert"]
        assert d["token_url"] and d["client_id"] and d["api_endpoint"] and d["grant_type_password"]

    def test_die_gepruefte_adresse_ist_die_gebaute(self):
        assert _fix()["api"]["gebaut"]["url"] == API_ENDPOINT


class TestNullbefund:
    def test_die_konstanten_sind_die_gemessenen(self):
        """Sonst prueft die Aufzeichnung etwas, das der Server nicht baut."""
        f = _fix()
        assert f["idp"]["gebaut"]["url"] == IDP_TOKEN_URL
        assert f["api"]["gebaut"]["url"] == API_ENDPOINT
        assert CLIENT_ID == "datadelivery-api-client", (
            "Die Doku nennt diesen Wert woertlich als «constant string»."
        )
