"""Die Modern-Aera (`2026-07-28`) an echten Antworten gemessen, nicht behauptet.

`tests/test_protocol_version.py` pinnt die beiden Revisionen gegen die
SDK-Konstanten und sagt selbst, dass das die schwaechere Form ist. Die
Begruendung dafuer stand in beiden READMEs — dieses Repo baue keine ASGI-App,
durch die sich eine Anfrage schicken liesse — und sie stimmte nicht:
`_build_http_app()` baut genau eine, und `tests/test_cors.py` schickt seit je
Anfragen hindurch. Eine Zusicherung, die sich mit «geht nicht» aus der Messung
heraushaelt, obwohl die Messung danebenliegt, ist die Bauart, vor der Teil 1
der CLAUDE.md warnt: nichts ist rot, weil nichts geprueft wird, worauf es
ankommt.

Hier laeuft deshalb der ganze Weg: JSON-RPC-Koerper mit `_meta`-Envelope, die
Routing-Header aus `mcp.shared.inbound`, durch Starlette, die
Transport-Security und den Session-Manager des SDK, und zurueck kommt das
Resultat, das ein echter Client saehe.

**Die Port-Falle.** `TestClient` spricht per Vorgabe `http://testserver` an,
und das SDK schaltet fuer `host="127.0.0.1"` von sich aus den
DNS-Rebinding-Schutz ein (`mcp/server/lowlevel/server.py`), dessen Muster
`"127.0.0.1:*"` einen Port VERLANGT: `base_host + ":"`. Ein Host-Header ohne
Port faellt durch. Beides zusammen beantwortet jede Anfrage mit
`421 Misdirected Request`, bevor ein MCP-Byte fliesst — ein Fehlerbild, das
wie ein Protokollproblem aussieht und keines ist. Darum die Basis-URL mit
Port. Wer sie kuerzt, misst wieder nichts.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from mcp.shared.inbound import (
    MCP_METHOD_HEADER,
    MCP_NAME_HEADER,
    MCP_PROTOCOL_VERSION_HEADER,
)
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    CLIENT_INFO_META_KEY,
    PROTOCOL_VERSION_META_KEY,
)
from mcp_types.jsonrpc import UNSUPPORTED_PROTOCOL_VERSION
from mcp_types.version import LATEST_HANDSHAKE_VERSION, MODERN_PROTOCOL_VERSIONS
from starlette.testclient import TestClient

from swiss_ip_mcp import __version__
from swiss_ip_mcp.server import PROJECT_URL, _build_http_app

MODERN_VERSION = "2026-07-28"
ENDPOINT = "/mcp"

# Siehe Docstring: der Port ist nicht kosmetisch, ohne ihn antwortet alles 421.
BASE_URL = "http://127.0.0.1:8000"

# SEP-2575: der Schluessel, unter dem die Server-Identitaet in jedem Resultat steht.
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"

# SEP-2549: die auflistenden Methoden, die `ttlMs`/`cacheScope` tragen muessen.
# `resources/read` steht bewusst nicht dabei — es braeuchte einen Netzzugriff,
# und dieser Modul ist unit, nicht live.
LISTING_METHODS = (
    "server/discover",
    "tools/list",
    "prompts/list",
    "resources/list",
    "resources/templates/list",
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Der zusammengebaute ASGI-Stack, mit laufendem Lifespan.

    Der Kontextmanager ist Pflicht und nicht Stil: ohne ihn startet der
    Streamable-HTTP-Session-Manager nicht und jede Anfrage endet im
    `RuntimeError: Task group is not initialized`.

    Die beiden Env-Variablen werden geleert, damit `_transport_security()`
    keine Allow-Liste baut: diese Datei misst das Protokoll, nicht SEC-005 —
    dafuer gibt es `tests/test_cors.py`.
    """
    monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    with TestClient(_build_http_app("streamable-http"), base_url=BASE_URL) as c:
        yield c


def modern_request(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    version: str = MODERN_VERSION,
    name: str | None = None,
) -> Any:
    """Eine Anfrage in der Form, die `2026-07-28` verlangt.

    Envelope im `_meta` der Params, Routing-Header auf der HTTP-Anfrage — die
    Header-Namen kommen aus dem SDK, damit eine Umbenennung dort hier auffaellt
    und nicht in einer Zeichenkette untergeht.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            **(params or {}),
            "_meta": {
                PROTOCOL_VERSION_META_KEY: version,
                CLIENT_INFO_META_KEY: {"name": "swiss-ip-mcp-tests", "version": "0"},
                CLIENT_CAPABILITIES_META_KEY: {},
            },
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        MCP_METHOD_HEADER: method,
        MCP_PROTOCOL_VERSION_HEADER: version,
    }
    if name is not None:
        headers[MCP_NAME_HEADER] = name
    return client.post(ENDPOINT, json=body, headers=headers)


def result_of(response: Any) -> dict[str, Any]:
    """Das `result` aus einer Antwort, die JSON oder SSE sein darf.

    Das SDK waehlt die Rahmung nach Methode und Accept-Kopf; welche es war,
    ist fuer die Zusicherungen hier ohne Belang, und ein Test, der an der
    Rahmung haengt, bricht beim naechsten SDK-Bump ohne Befund.
    """
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:400]}"
    text = response.text
    if text.lstrip().startswith("event:"):
        text = next(line[len("data: ") :] for line in text.splitlines() if line.startswith("data: "))
    payload = json.loads(text)
    assert "error" not in payload, payload["error"]
    return payload["result"]


# ---------------------------------------------------------------------------
# Die Aera antwortet ueberhaupt
# ---------------------------------------------------------------------------


def test_ein_moderner_request_wird_bedient(client: TestClient) -> None:
    """Der lasttragende Test: `2026-07-28` kommt durch den ganzen Stack.

    Faellt er, spricht der Server die Aera nicht mehr — und zwar unabhaengig
    davon, was die SDK-Konstanten behaupten.
    """
    result = result_of(modern_request(client, "tools/list"))
    assert result["tools"], "tools/list liefert in der Modern-Aera nichts"


@pytest.mark.parametrize(
    ("label", "params", "extra_headers"),
    [
        ("ohne Envelope", {}, {MCP_METHOD_HEADER: "tools/list", MCP_PROTOCOL_VERSION_HEADER: MODERN_VERSION}),
        ("ohne Routing-Header", None, {}),
    ],
)
def test_ein_halber_moderner_request_wird_nicht_bedient(
    client: TestClient, label: str, params: dict[str, Any] | None, extra_headers: dict[str, str]
) -> None:
    """Die Gegenprobe zum Test darueber: misst der wirklich die Modern-Aera?

    `tools/list` gibt es in beiden Aeren. Ein gruenes `tools/list` allein
    belegt also gar nichts — es koennte ueber die Legacy-Aera gekommen sein,
    und der Test daruber waere eine Zusicherung, die auch dann haelt, wenn
    `2026-07-28` gar nicht bedient wird.

    Hier faellt je eine der beiden Haelften weg. Gemessen antwortet beides mit
    HTTP 400, aus verschiedenen Gruenden: ohne `_meta`-Envelope lehnt die
    moderne Leiter mit `-32602` ab und nennt den fehlenden Schluessel; ohne
    Routing-Header faellt die Anfrage in die Legacy-Aera und scheitert dort an
    der fehlenden Session. Beide Wege sind zu, also braucht der gruene Fall
    beide Haelften — und misst damit die Aera und nicht bloss die Methode.
    """
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    if params is None:
        body["params"] = {
            "_meta": {
                PROTOCOL_VERSION_META_KEY: MODERN_VERSION,
                CLIENT_INFO_META_KEY: {"name": "swiss-ip-mcp-tests", "version": "0"},
                CLIENT_CAPABILITIES_META_KEY: {},
            }
        }
    else:
        body["params"] = params

    response = client.post(
        ENDPOINT,
        json=body,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **extra_headers,
        },
    )
    assert response.status_code == 400, f"{label}: mit HTTP {response.status_code} bedient"


def test_server_discover_nennt_die_modernen_versionen(client: TestClient) -> None:
    """`server/discover` ist in dieser Revision Pflicht («servers MUST implement»).

    Gemessen statt aus der Registrierung geschlossen: die Methode kommt vom
    SDK, nicht aus diesem Repo, und genau deshalb kann ein Bump sie
    wegnehmen, ohne dass hier eine Zeile anders aussieht.
    """
    result = result_of(modern_request(client, "server/discover"))
    assert result["supportedVersions"] == list(MODERN_PROTOCOL_VERSIONS)
    assert MODERN_VERSION in result["supportedVersions"]


# ---------------------------------------------------------------------------
# SEP-2575 — Server-Identitaet in JEDEM Resultat
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", LISTING_METHODS)
def test_jedes_resultat_traegt_die_server_identitaet(client: TestClient, method: str) -> None:
    """«servers SHOULD identify themselves in each result's `_meta`» (SEP-2575).

    Der Grund, warum das je Methode geprueft wird und nicht einmal: Die
    Identitaet steht in dieser Aera nicht mehr einmalig im `initialize`-
    Ergebnis, sondern in jeder einzelnen Antwort. Eine Stichprobe auf einer
    Methode koennte gruen sein, waehrend die anderen sie nicht tragen.
    """
    meta = result_of(modern_request(client, method)).get("_meta", {})
    info = meta.get(SERVER_INFO_META_KEY)
    assert info is not None, f"{method} traegt keine Server-Identitaet"
    assert info["name"] == "swiss_ip_mcp"
    assert info["version"] == __version__
    assert info["websiteUrl"] == PROJECT_URL


def test_die_projektadresse_ist_dieselbe_wie_im_registry_manifest() -> None:
    """`websiteUrl` steht an zwei Stellen und muss dieselbe Adresse nennen.

    Der Server meldet sie im Protokoll (`PROJECT_URL`), `server.json` meldet sie
    der MCP-Registry. Zwei Publikum, eine Aussage — laufen sie auseinander,
    zeigt die Registry auf das eine und jeder verbundene Client auf das andere,
    und nichts faellt auf.

    Diese Zusicherung ist mit `PROJECT_URL` entstanden: davor war die Adresse
    im Code nur Teil des User-Agent-Strings und keine eigene Angabe. Wer eine
    zweite Quelle schafft, haengt das Gate gleich daneben — sonst ist es die
    naechste Drift, die jemand in einem halben Jahr entdeckt.
    """
    manifest = json.loads((pathlib.Path(__file__).resolve().parents[1] / "server.json").read_text(encoding="utf-8"))
    assert manifest["websiteUrl"] == PROJECT_URL


def test_die_gemeldete_version_ist_nicht_leer(client: TestClient) -> None:
    """Der Befund, der diese Datei ausgeloest hat — als eigener Test.

    `MCPServer` hat fuer `version` den Default `""`, und der galt hier: der
    Server wies sich bei jedem Aufruf als versionslos aus, waehrend dieselbe
    Nummer im User-Agent an die Datenquelle ging.

    Steht eigens neben dem Test darueber, weil dieser gegen `__version__`
    prueft: waere `__version__` selbst je leer, ginge jener gruen durch und
    die Zusicherung waere still verschwunden.
    """
    info = result_of(modern_request(client, "tools/list"))["_meta"][SERVER_INFO_META_KEY]
    assert info["version"].strip(), "der Server meldet eine leere Version"


# ---------------------------------------------------------------------------
# SEP-2322 / SEP-2549 — Resultat-Form der Revision
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", LISTING_METHODS)
def test_jedes_resultat_traegt_resulttype(client: TestClient, method: str) -> None:
    """SEP-2322: «All results now carry a required `resultType` field»."""
    assert result_of(modern_request(client, method))["resultType"] == "complete"


@pytest.mark.parametrize("method", LISTING_METHODS)
def test_die_cache_hints_kommen_auf_der_leitung_an(client: TestClient, method: str) -> None:
    """SEP-2549 an der Antwort gemessen, nicht am `CACHE_HINTS`-Dict.

    `tests/test_cache_hints.py` prueft die Konfiguration; dass sie das SDK
    erreicht und in der Antwort landet, kann nur diese Seite zeigen. Genau
    diese Luecke — vollstaendige Liste, die nie an der Mechanik ankommt —
    hatte `tests/test_cors.py` schon einmal im Nachbarthema.
    """
    result = result_of(modern_request(client, method))
    from swiss_ip_mcp.server import LIST_CACHE_TTL_MS

    assert result["ttlMs"] == LIST_CACHE_TTL_MS
    assert result["cacheScope"] == "public"


# ---------------------------------------------------------------------------
# Die Aera-Trennung, die der Server verspricht
# ---------------------------------------------------------------------------


def test_der_handshake_handelt_die_dokumentierte_revision_aus(client: TestClient) -> None:
    """Die Legacy-Aera gemessen — das, was die READMEs bisher nur behaupteten.

    Heutige Clients sprechen diese Aera; sie ist der lasttragende Pin. Bisher
    stand dafuer eine Zusicherung ueber eine SDK-Konstante, mit der Begruendung,
    ein echtes `initialize` sei hier nicht zu schicken. Hier ist es.
    """
    response = client.post(
        ENDPOINT,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_HANDSHAKE_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "swiss-ip-mcp-tests", "version": "0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    result = result_of(response)
    assert result["protocolVersion"] == LATEST_HANDSHAKE_VERSION
    assert result["serverInfo"]["version"] == __version__


def test_eine_unbekannte_revision_bekommt_die_liste_der_unterstuetzten(client: TestClient) -> None:
    """Der Weg, auf dem ein Client dieser Aera sich korrigieren kann.

    Ohne `initialize` gibt es keine Aushandlung: Die Spec laesst den Server
    jede Anfrage einzeln annehmen oder mit `UnsupportedProtocolVersionError`
    ablehnen, und der Client waehlt aus dem mitgelieferten `supported` eine
    gemeinsame Revision. Faellt dieses Feld weg, hat ein Client mit falscher
    Annahme keinen zweiten Versuch — die Verbindung ist tot, ohne dass ein Gate
    etwas meldet.

    Erste Fassung dieses Tests sicherte nur zu, dass die Anfrage «nicht als
    gueltiges Resultat durchgeht», und verpackte auch das in ein
    `if status == 200`. Gemessen antwortet das SDK mit HTTP 400 — der Zweig lief
    also nie, und der Test waere auch dann gruen geblieben, wenn der Server
    erfundene Revisionen klaglos bedient haette. Genau die Bauart, gegen die
    diese Datei geschrieben ist.

    `-32022` steht hier als Zahl, weil die Spec sie festschreibt
    (Fehlercode-Allokation, `-32020`…`-32099` fuer die Spec reserviert). Der
    Abgleich mit der SDK-Konstante steht daneben: liefe eins vom anderen weg,
    soll das hier auffallen und nicht stumm mitwandern.
    """
    response = modern_request(client, "tools/list", version="1900-01-01")
    assert response.status_code == 400, f"erfundene Revision mit HTTP {response.status_code} bedient"

    error = json.loads(response.text)["error"]
    assert error["code"] == -32022 == UNSUPPORTED_PROTOCOL_VERSION
    assert error["data"]["requested"] == "1900-01-01"
    assert MODERN_VERSION in error["data"]["supported"]
