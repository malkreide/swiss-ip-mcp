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

**Ein 4xx ist kein Nein.** Am 29.8.2026 antwortete `past-publications` in
`swiss-procurement-mcp` auf jede Publikation mit Losen mit HTTP 400. Daraus war
geschlossen worden, die Quelle verweigere diese Auskunft; der Befund stand
datiert im Fixture-Nachweis, ein Test bestätigte ihn, alles blieb grün. Die
Spec desselben Endpunkts führt einen als *optional* deklarierten Parameter
`lotId` — für Publikationen mit Losen ist er Pflicht. Mit ihm antwortet
dieselbe Publikation mit 200. Ein Projekt trug sieben Vorgängerpublikationen,
die der Server als «Quelle nicht erreichbar» wegwarf.

Drei Handgriffe daraus:

- **Die Parameterliste der Spec durchgehen, bevor ein Statuscode eingeordnet
  wird.** «Optional» heisst dort oft «optional für die Mehrheit».
- **Einer deterministischen Absage keinen Wiederholungsrat geben.** «Nicht
  erreichbar, bitte später erneut» ist bei einem 400 falsch und liest sich für
  das Modell wie eine Störung. Den Status mitführen und den fehlenden
  Parameter benennen — den Status, nicht den Antwortkörper.
- **Beide Antworten aufzeichnen, mit und ohne den Parameter.** Eine
  Aufzeichnung nur des Fehlschlags kann nicht zeigen, dass er vermeidbar war;
  dass nur der 400er aufgezeichnet war, ist der Grund, warum der falsche
  Befund nicht auffiel.

**Und ein 403 ist gar keine Auskunft.** Am 29.8.2026 sollten für 42 Repos die
Dependabot-Labels nachgemessen werden. Alle 13 Abfragen des ersten Stapels
kamen zurück als:

```
Failed to find label: API rate limit already exceeded for user ID 8864492.
```

Der gefährliche Teil steht vorn: Das Werkzeug verpackt eine Sperre als
Fund-Fehlschlag. Wer die Zeile überfliegt oder nur auf ein leeres Ergebnis
prüft, zählt 39 Repos als «Label fehlt» und hat seine eigene Erschöpfung
gemessen. Das Limit hängt am Konto, nicht am Repo — derselbe Vormittag hatte
es mit 42 eröffneten und 42 gemergten PRs verbraucht.

Das ist der Absatz darüber, andersherum gelesen: dort war ein 400 eine echte,
wiederholbare Antwort und galt als Störung; hier ist eine Störung als Antwort
verpackt. Entscheidend ist nie der Statuscode, sondern ob die Quelle überhaupt
geantwortet hat.

- **Positivkontrolle im selben Repo.** Ein «nicht gefunden» wird erst dadurch
  zur Messung, dass eine gleichzeitige Abfrage etwas findet.
- **Die Messung entlang der Sperre teilen.** `raw.githubusercontent.com` ist
  ein CDN und nicht die REST-API. Um 11:19:27 UTC lieferte es für
  `register-mcp` HTTP 200, während die Label-Abfrage desselben Repos in
  derselben Minute die Sperre meldete. Alle 42 `dependabot.yml` kamen so
  durch, während die Label-Hälfte stand.
- **Am Token vorbei geht es nicht.** Beide Umwege enden am Agent-Proxy, und
  jeder mit einer eigenen irreführenden Begründung. `api.github.com` ohne
  Zugangsdaten:

  ```
  GitHub access is not enabled for this session. An org admin must connect
  the Claude GitHub App for this organization.
  ```

  Das ist keine Aussage über die Organisation, sondern das, was ohne Token
  kommt. Wer ihr folgt, sucht einen Admin für ein Problem, das keiner hat.
  Die HTML-Seite `github.com/<owner>/<repo>/labels` fällt ebenfalls, aber
  anders:

  ```
  This GitHub API path is not available: sessions are bound to their
  configured repositories. Use repository-scoped endpoints
  (repos/{owner}/{repo}/...).
  ```

  Der Proxy behandelt also auch `github.com` als API-Pfad; die zweite Meldung
  klingt nach einem Scope-Problem und ist doch nur dieselbe Sackgasse. Den
  Token aus der Umgebung in einen curl-Header zu setzen, blockiert der
  Klassifikator. Ob es überhaupt hülfe, ist offen: die Sperre nennt ein
  Nutzerkonto, und ob der Token zu diesem gehört, wurde nie geprüft.
- **Die Sperre gilt nicht dem Dienst, sondern dem Zugangspfad.** Unmittelbar
  nachdem eine Abfrage der Checks eines PR sauber durchlief, meldete die
  Label-Abfrage weiter die Sperre. Von einem blockierten Werkzeug also nicht
  auf «GitHub ist zu» schliessen — und umgekehrt eine gelungene Abfrage nicht
  als Entwarnung für die gesperrte nehmen.

Wann die Sperre fällt, geben diese Beobachtungen nicht her. Die Meldung nennt
keinen Zeitpunkt, und die `X-RateLimit`-Kopfzeilen sind hinter dem Proxy nicht
zu sehen. Belegt sind drei gesperrte Zeitpunkte — 11:14, 11:16 und 11:19 UTC.
Wer daraus eine Dauer macht, hat sie erfunden.

**Dieselbe Falle bei einer Konfigurationsoption: die Vorgabe lesen, bevor man
einen Schlüssel für wirkungslos hält.** Am 29.8.2026 fielen die
`labels:`-Zeilen aus den `dependabot.yml` des Portfolios, begründet mit
«Dependabot legt Labels nicht an». Eine Messung danach zeigte, dass
`dependencies` in 36 von 42 Repos sehr wohl existiert, 35 davon mit GitHubs
Standardbeschreibung. Das las sich zuerst wie ein Beleg, dass die Aktion
falsch war.

Die Optionsreferenz kehrt es um:

```
Dependabot creates these default labels automatically, as necessary in
your repository.

If you define more than one package manager, an additional label for the
ecosystem or language is added to each pull request.

The labels specified are used instead of the default labels.
```

Ohne `labels:` vergibt Dependabot also `dependencies` — und, sobald mehr als
ein Paketmanager deklariert ist, zusätzlich ein Ökosystem-Label — und legt sie
selbst an; eine eigene Liste **ersetzt** diesen Satz, und «if any of these
labels is not defined in the repository, it is ignored». Die Zeile war nicht
wirkungslos — sie tauschte einen sich selbst pflegenden Vorgabesatz gegen eine
starre Liste.

**Die Bedingung nicht weglassen.** Bei nur einem Paketmanager steht das
Ökosystem-Label gar nicht zu; wer es dort trotzdem erwartet, schreibt genau
den Fehlbefund auf, gegen den dieser Abschnitt geschrieben ist — der Abschnitt
liefe an sich selbst vorbei. Im Portfolio deklariert jede `dependabot.yml`
zwei (`pip` und `github-actions`), die Bedingung ist hier also überall
erfüllt; anderswo nicht unbedingt. Aufgefallen ist die fehlende Bedingung
nicht beim Schreiben, sondern durch einen Codex-Review auf
`swiss-environment-mcp` PR #113 — vierzehn Sekunden vor dem Merge desselben
PR.

Was das kostet, ist an `openlex-mcp` gemessen: zwei Ökosysteme deklariert,
also stünden `dependencies` **und** ein Ökosystem-Label zu; vorhanden ist nur
das erste, `github-actions` und `github_actions` fehlen beide (Kontrolle `bug`
vorhanden). `register-mcp` ist die Gegenprobe: dort existieren alle vier
deklarierten Namen mit handgeschriebener Beschreibung, die Liste ist gewollt
und vollständig.

**Dreimal falsch eingeordnet, in drei Richtungen.** Erst die Zeile für bloss
wirkungslos gehalten. Dann die gefundenen Labels für einen Widerspruch. Dann,
auf denselben Fund gestützt, einen richtigen PR geschlossen mit dem Argument,
das Label existiere ja — obwohl es existiert, *weil* die Vorgabe es anlegt.
Der dritte Fehler ist der teuerste, weil er wie eine Messung aussah.

Was die Messung **nicht** hergibt: wer die 36 Labels angelegt hat. Die
Referenz sagt, Dependabot tue es; die Objekt-IDs liegen aber so dicht
beieinander, dass sie eher aus einem Stapellauf stammen. Beides passt zum
Befund, keines ist belegt — die Herkunft blieb ungemessen.

Beim Aufräumen gilt deshalb dieselbe Frage wie bei `lotId`: Was ist die
*Vorgabe*, wenn man das Ding weglässt — nicht bloss, ob der aktuelle Wert
etwas bewirkt.

**`results[0]` ist nur so verlässlich wie die Zusicherung danach.** Pinnt die
Abfrage einen bekannten Datensatz, ist der erste Treffer eine Drift-Wache und
in Ordnung. Hängt die Zusicherung dagegen davon ab, *welche* Variante die
Quelle heute zuoberst hat, prüft der Test den Tag: am 25.8.2026 rot, weil die
neueste Zürcher Publikation zufällig Lose hatte, am 26.8. grün, ohne dass sich
etwas geändert hätte. Den Fall gezielt wählen und beide Zweige fahren.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — Dieses Repo

**ruff: eine Quelle.** `pyproject.toml`, `dev`-Extra, ein exakter
`ruff==`-Pin — die Version dort nachlesen, nicht hier: Diese Zeile nannte sie
wörtlich und stand am 8.9.2026 auf `0.16.3`, während `pyproject.toml` längst
`0.16.4` führte. Eine zweite Quelle in einem Absatz namens «eine Quelle». Die CI
hat keinen eigenen Pin-Schritt — der Install über `ci.yml` genügt, lokal wie
dort. Eine `.pre-commit-config.yaml` gibt es nicht; wenn eine dazukommt, muss
sie dieselbe Version aus `pyproject.toml` beziehen und keine zweite nennen.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

Meldet `scripts/check_ruff_pin.py` genau das, hilft ein zweiter `pip install`
nicht: das ältere Binary bleibt vorne im `PATH`. Die Gates dann über das Modul
fahren — `python -m ruff check …`, `python -m ruff format --check …`. Am
18.8.2026 lagen so 0.15.8 (PATH) und 0.16.1 (Modul) nebeneinander; `ruff
format --check` war mit beiden grün, was den Unterschied nicht widerlegt.

`line-length = 120` steht unter `[tool.ruff]`. Im Portfolio stehen daneben 88
und 100: aus einem anderen Server kopierter Code ist hier lint-sauber und
fällt trotzdem bei `ruff format --check` um.

**Gates, wörtlich aus `ci.yml`** (Matrix: Python 3.11 / 3.12 / 3.13):

```
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_ip_mcp/server.py
pytest tests/ -m "not live" -v
python scripts/check_version_sync.py
```

**Kein `include` unter `[tool.ruff]` setzen.** Hier stand
`include = ["src/**/*.py"]`, während das Gate `src/ tests/ scripts/` nennt:
ruff verengte den Umfang still auf `src/` und prüfte 5 von 14 Dateien. Der
Befehl sagte das eine, geprüft wurde das andere, und nichts widersprach —
`tests/` und `scripts/` sammelten dabei 4 Lint-Fehler und 4
Format-Abweichungen an. Der Umfang sind die drei Pfade im Gate-Befehl selbst.
Wer ihn prüfen will, zählt nach statt hier abzulesen:
`ruff check src/ tests/ scripts/ --show-files | wc -l`.

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

**Der Live-Job ist rot, und das ist die richtige Antwort.** Die Secrets
`IGE_USERNAME` / `IGE_PASSWORD` sind im Repo nicht gesetzt; ohne sie
überspringt jeder der vier Live-Tests (`skipif(not LIVE)`, `LIVE =
_live_enabled()`). Bis zum 24.8.2026 meldete der Job dafür Erfolg — zehn grüne
wöchentliche Läufe, in denen nichts gegen swissreg.ch geprüft wurde. Seit
`ab38c24` ist er rot. Grün wird er nicht durch eine Änderung an `live.yml`,
sondern durch die Secrets. Wer die Fehlermeldung des Jobs für den Fehler hält
und `live.yml` daraufhin repariert, repariert den Melder.

**Ein halb gesetztes Secret ist schlimmer als gar keines.** Die Schranke im
Workflow und die Marke in `tests/test_server.py` fragten beide allein nach
`IGE_USERNAME`, `_load_credentials` verlangt aber Benutzername **und**
Passwort. Wer nur den Benutzernamen setzt, kommt an beiden vorbei, die vier
Live-Tests laufen los und fallen geschlossen an einem `ToolError` — und die
Einordnung sieht Fehler im JUnit-XML, meldet `finding` und lässt ein Issue
aufgehen, das swissreg.ch einen gebrochenen Vertrag unterstellt. Ein fehlendes
Secret ist kein Befund über die Quelle; beides prüft jetzt beide Variablen,
und der richtige Befund bleibt `unknown`.

Die erste Fassung dieser Meldung war trotzdem falsch: Der Nicht-Lauf reichte
`--pytest-exit 127` durch, und die Einordnung machte daraus «pytest ist nicht
bis zum Schreiben gekommen (Exit 127)». 127 heisst «command not found» — der
Job behauptete einen gescheiterten pytest-Aufruf, den es nie gab, und schickte
den Leser hinter einem fehlenden Binary her. Wer einen Zustand meldet, den er
selbst herbeigeführt hat, benennt ihn; ein geliehener Exit-Code ist kein Grund.
Dafür gibt es jetzt `--not-started`.

Und die zweite Fassung sagte «Unvollständige IGE-Zugangsdaten» auch dann, wenn
gar nichts gesetzt war — also im einzigen Fall, den das Repo tatsächlich hat.
Der Absatz darüber lebt vom Unterschied zwischen halb und gar nicht, die
Meldung ebnete ihn wieder ein: Wer «unvollständig» liest, sucht die zweite
Hälfte eines Secrets, das nie eine erste hatte. Der Text nennt jetzt beide
Lagen getrennt.

**Und der Melder selbst kann sich überschreiben.** Der Schritt «Ergebnis
einordnen» hängte die letzten vierzig Zeilen der pytest-Ausgabe über einen
Heredoc mit dem festen Trennwort `PYTEST_TAIL` an `$GITHUB_OUTPUT` an — in
dieselbe Datei, in die `classify_live_run.py` eine Zeile vorher `state=` und
`reason=` geschrieben hat. Steht in der Ausgabe eine Zeile `PYTEST_TAIL`, endet
der Block dort, und der Runner liest den Rest als weitere Outputs. Nachgestellt
am 8.9.2026: aus `state=unknown` wurde `state=clear`, der rote Lauf wäre grün
geworden und hätte das offene Issue geschlossen. Die pytest-Ausgabe ist fremder
Text — dieselbe Begründung, die im Skript-Schritt darunter schon zweimal steht,
nur eine Ebene tiefer. Das Trennwort wird jetzt je Lauf zufällig gezogen.
