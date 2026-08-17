# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — Dieses Repo


**ruff: eine Quelle.** `pyproject.toml`, `dev`-Extra, `ruff==0.16.1`. Die CI
hat keinen eigenen Pin-Schritt — der Install über `ci.yml` genügt, lokal wie
dort. Eine `.pre-commit-config.yaml` gibt es nicht; wenn eine dazukommt, muss
sie dieselbe Version aus `pyproject.toml` beziehen und keine zweite nennen.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

**Gates, wörtlich aus `ci.yml`** (Matrix: Python 3.11 / 3.12 / 3.13):

```
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_ip_mcp/server.py
pytest tests/ -m "not live" -v
python scripts/check_version_sync.py
```

Der `py_compile`-Schritt fehlte hier, obwohl der Block «wörtlich» heisst — er
steht in `ci.yml` zwischen Format-Check und Tests. Alle fünf laufen im Job
`quality` auf allen drei Versionen, keine `if:`-Ausnahme; ein
`fail-fast: false` steht nicht da.

**Der pytest-Schritt war bedingt — seit diesem Commit nicht mehr.** In
`ci.yml` stand er als `if [ -d "tests" ]; then pytest …; else echo "No tests
directory found, skipping."; fi`. Verschwand `tests/`, gab der Schritt Exit 0
und der Lauf wurde grün, ohne einen einzigen Test gefahren zu haben — ein
grüner Haken, der «nichts geprüft» bedeutet.

Jetzt läuft `pytest` ohne Bedingung. Fehlt `tests/`, endet es mit 4; sammelt
es nach `-m "not live"` nichts ein, mit 5. Beides ist rot, und beides ist die
richtige Antwort: Ein Unit-Gate ohne Unit-Tests hat nichts zugesichert.

Den Zweig nicht zurückholen. Übersprungen ist nicht bestanden (OPS-005), und
ein Verzeichnis, dessen Fehlen kein Gate rot macht, ist genau die Bauart, vor
der Teil 1 warnt.

**`secret-scan.yml` gatet ebenfalls jeden PR** und stand in keiner Liste.
Lokal stellt ihn keiner der Befehle oben nach.

**Live-Tests: geplanter Workflow vorhanden.** `.github/workflows/live.yml`,
`cron: "0 3 * * 1"` plus `workflow_dispatch`. Die Live-Suite ist also nicht bloss
per `-m "not live"` ausgeschlossen — DRIFT-005 ist hier erfüllt. `schedule`
greift nur auf dem Default-Branch (`main`): Änderungen am Workflow wirken erst
nach dem Merge, vorher von Hand per `workflow_dispatch`.
