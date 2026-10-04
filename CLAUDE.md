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

**Bei einem blockierten PR nennt der Merge-Versuch den Blocker, jede Ableitung
rät.** `mergeable_state: blocked` bei grüner CI heisst: ein required Kontext
fehlt oder steht nicht auf grün. Welcher, sagt die Einstellung — und die sperrt
der Agent-Proxy mit HTTP 403, ein MCP-Werkzeug dafür gibt es nicht. Der Ausweg
ist nicht Indizienarbeit, sondern ein Merge-Versuch über die API:

```
PUT /repos/<owner>/<repo>/pulls/<n>/merge
405 Required status check "Codex hat diesen Head geprueft" is expected.
```

Der Name steht dort wörtlich so, wie er in der Branch Protection eingetragen
ist. Scheitert der Versuch, kostet er nichts.

Am 24./25.9.2026 über drei Repos vermessen, nachdem ein Gate-Workflow entfernt
worden war und seinen required Kontext ohne Berichterstatter zurückliess:

| Repo | eingetragener Kontext | Art |
|---|---|---|
| `register-mcp` | `Codex hat den PR angesehen` | Check-Run |
| `srgssr-mcp` | `review-abgeschlossen` | Check-Run |
| `fedlex-mcp` | `Codex hat diesen Head geprueft` | Check-Run |

**Warum Ableiten hier systematisch fehlgeht.** GitHub nimmt als Check-Run-Name
den **Job**-Namen, nicht den des Workflows. Zwei der drei Kontexte enthalten die
Zeichenfolge «codex-gate» nicht, obwohl sie aus `codex-gate.yml` stammen; wer in
den Einstellungen danach sucht, findet nichts und hält die Regel für abwesend.
Trug der Job kein `name:`, nimmt GitHub die Job-ID — daher `review-abgeschlossen`.

Zwei Fehlschlüsse sind dabei belegt, beide aus **einer** Beobachtung gezogen:

- Aus einem Commit-Status auf den required Kontext geschlossen. In `fedlex-mcp`
  stand der Status `codex-gate` auf dem Head auf `success` und blockierte
  nichts, während der fehlende Check-Run den Merge hielt. Am Kontroll-PR waren
  beide rot — dort ist nicht zu unterscheiden, welcher von beiden eingetragen
  ist. Genommen wurde der auffälligere.
- Aus einer Check-Run-Liste auf den required Kontext geschlossen. Die Liste
  zeigt, was **berichtet** wurde; eingetragen sein kann ein Name, der gerade
  gar nicht erscheint. Genau das ist der Fall, um den es geht.

**Ein Vorbehalt, der zur Methode gehört:** Die Absage nennt immer nur den
**ersten** fehlenden Kontext. Ist ein zweiter eingetragen, zeigt ihn erst der
nächste Versuch. Nach jeder Änderung an der Einstellung also erneut versuchen,
bis der Merge durchgeht oder ein neuer Name fällt.

Die Kosten der Ableitung sind gemessen: ein Arbeitstag, an dem der PR-Text den
falschen Namen trug und in den Einstellungen nach einer Zeichenfolge gesucht
wurde, die dort nicht steht.

**Ein Review, der nicht eingetragen ist, hält nichts auf — auch wenn er
läuft.** Codex startet unter anderem beim Auslöser «Draft marked ready». Am
4.10.2026 über die vier PRs jenes Tages in `swiss-ip-mcp` gemessen:

| PR | Review angekündigt | «Completed» | gemergt | Verdikt nach dem Merge |
|---|---|---|---|---|
| #94 | 11:28:47 | 11:29:44 | 11:28:49 | +55 s |
| #95 | 13:00:37 | 13:01:27 | 13:00:34 | +53 s |
| #96 | 14:31:02 | 14:32:08 | 14:30:57 | +71 s |
| #97 | 16:14:19 | 16:15:14 | 16:14:32 | +42 s |

Der Review braucht 50 bis 71 Sekunden, und das Draft-Flag fiel jedes Mal in
derselben Minute wie der Merge. Viermal von vier kam das Verdikt also
hinterher; bei #95 und #96 war der PR schon zu, bevor der Bot sich überhaupt
gemeldet hatte.

Dass er nichts aufhält, ist gemessen und nicht geschlossen: Um 16:14, während
der Review lief und nichts berichtet hatte, stand #97 auf
`mergeable_state: clean`. Ein fehlender required Kontext hätte `blocked`
ergeben — genau die Unterscheidung aus dem Absatz darüber. Der Merge selbst
taugt als Beleg nicht: Ihn führte ein Mensch aus, der eine Branch Protection
überstimmen kann.

**Was die Messung nicht hergibt, ist der Preis.** Alle vier Reviews endeten
ohne Fund (👍 statt Kommentar), verloren ist also nichts. Der Fall mit dem Fund
steht weiter oben und war Glück: Auf `swiss-environment-mcp` PR #113 kam der
Befund vierzehn Sekunden vor dem Merge an — dieselbe Minute, andere Seite der
Ziellinie.

Daraus folgt nicht «langsamer mergen», sondern eine Unterscheidung: Ein Bot,
der nach dem Merge urteilt, ist Dokumentation und kein Gate. Wer ihn als Gate
will, trägt ihn als required Kontext ein; wer ihn als Dokumentation behält,
darf seinen grünen Haken nicht als «geprüft» lesen.

**Und die erste Fassung dieser Beobachtung war selbst ein Fehlschluss.** Sie
stand auf dem Kommentartext, der im Ereignis mitkam («Running since
16:14:16»), und schloss daraus, der Review sei nie zu einem Befund gekommen.
Der Bot schreibt aber denselben Kommentar fort: Objekt `5981975465` trug 42
Sekunden später «Completed». Ein Ereignis ist eine Momentaufnahme, keine
Auskunft über den Stand — wer es liest statt die Quelle, liest den Stand von
damals.

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

### Gates und ihre Fallen

**Gates, wörtlich aus `ci.yml`** (Job `quality`, Matrix 3.11 / 3.12 / 3.13,
keine `if:`-Ausnahme, kein `fail-fast: false`):

```
python scripts/check_ruff_pin.py
actionlint -verbose
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_ip_mcp/server.py
pytest tests/ -m "not live" -v
python scripts/check_version_sync.py
```

`secret-scan.yml` gatet ebenfalls jeden PR, steht in keiner dieser Zeilen und
lässt sich lokal mit keinem der Befehle nachstellen.

**ruff: eine Quelle.** Der exakte `ruff==`-Pin steht im `dev`-Extra von
`pyproject.toml` — die Version dort nachlesen, nicht hier: Diese Zeile nannte
sie wörtlich und stand am 8.9.2026 auf `0.16.3`, während `pyproject.toml`
längst `0.16.4` führte. Eine zweite Quelle in einem Absatz namens «eine
Quelle». Kommt eine `.pre-commit-config.yaml` dazu, muss sie dieselbe Version
beziehen und keine zweite nennen.

Ein älteres ruff früher im `PATH` schlägt den Pin, ohne dass der Install etwas
meldet. Meldet `scripts/check_ruff_pin.py` genau das, hilft ein zweiter
`pip install` nicht — dann die Gates über das Modul fahren
(`python -m ruff check …`). Am 18.8.2026 lagen so 0.15.8 (PATH) und 0.16.1
(Modul) nebeneinander, und `ruff format --check` war mit beiden grün: Das
widerlegt den Unterschied nicht.

`line-length = 120` steht unter `[tool.ruff]`; im Portfolio stehen daneben 88
und 100. Aus einem anderen Server kopierter Code ist hier lint-sauber und
fällt trotzdem bei `ruff format --check` um.

**Kein `include` unter `[tool.ruff]` setzen.** Hier stand
`include = ["src/**/*.py"]`, während das Gate `src/ tests/ scripts/` nennt:
ruff verengte den Umfang still auf 5 von 14 Dateien, und `tests/` und
`scripts/` sammelten 4 Lint-Fehler und 4 Format-Abweichungen an. Der Befehl
sagte das eine, geprüft wurde das andere, und nichts widersprach. Der Umfang
sind die drei Pfade im Gate selbst; nachzählen statt hier ablesen:
`ruff check src/ tests/ scripts/ --show-files | wc -l`.

**Der pytest-Schritt läuft ohne Bedingung, und das bleibt so.** Er stand als
`if [ -d "tests" ]; then pytest …; else echo "… skipping."; fi` — verschwand
`tests/`, gab er Exit 0 und der Lauf wurde grün, ohne einen Test gefahren zu
haben. Jetzt endet pytest ohne `tests/` mit 4 und bei leerer Sammlung mit 5;
beides rot, beides richtig. Übersprungen ist nicht bestanden (OPS-005).

**actionlint prüft nur so viel, wie im `PATH` liegt.** Für `run:`-Blöcke ruft
es `shellcheck`, für Python-Blöcke `pyflakes`; fehlt eines, schaltet es die
Regel ab und endet trotzdem mit 0. Deshalb liegt `shellcheck-py` im
`dev`-Extra; `pyflakes` fehlt überall, die Regel ist also überall aus. Wer
wissen will, was lief, liest die `Rule … was disabled`-Zeilen von
`actionlint -verbose` statt den grünen Haken.

**Keine Ausdrucks-Klammern in Kommentaren innerhalb von `run:`.** GitHub
wertet `${{ … }}` im ganzen Block aus, auch in Shell-Kommentarzeilen;
YAML-Kommentare ausserhalb sind unkritisch. Ein leeres Paar in `live.yml`
(`8aff614`, 8.9.2026) machte die Datei ungültig, und das Symptom sieht nicht
nach Syntaxfehler aus: ein roter Lauf ohne einen einzigen Job, benannt nach dem
Dateipfad statt «Live Tests» — obwohl die Datei keinen `push`-Auslöser hat. Der
Schaden war leise: Die Wochenläufe vom 14.9. und 21.9. fanden nicht statt.
`yaml.safe_load` merkt davon nichts, `actionlint` schon — seit 25.9.2026 Gate.

### Vor einem Release

**Die Laufzeitabhängigkeiten der Wheels vergleichen, nicht die Commits.**
`check_version_sync.py` hält fünf Versionsstellen gleich; ob eine Änderung,
die Nutzer trifft, im CHANGELOG steht, prüft nichts. Bei 1.2.0 fiel erst beim
Versionssprung auf, dass `mcp[cli]` aus `dependencies` ins `dev`-Extra
gewandert war (`8a6e346`, kein Eintrag) — jede Installation verliert damit den
`mcp`-Befehl.

Die Commit-Liste taugt nicht als Raster: Seit `v1.1.6` fassten zwölf Commits
`src/` oder `pyproject.toml` an, zehn ohne CHANGELOG, neun davon zu Recht
(ruff-Pins, CI, Formatierung). Entscheidend ist der Abschnitt, nicht die Datei,
und den zeigt das gebaute Paket:

```bash
pip download --no-deps "swiss-ip-mcp==<letzte Version>" -d /tmp/alt
python -m build --wheel --outdir /tmp/neu
for w in /tmp/alt/*.whl /tmp/neu/*.whl; do unzip -p "$w" '*/METADATA' | grep '^Requires-Dist' | grep -v 'extra ==' | sort > "$w.req"; done
diff /tmp/alt/*.req /tmp/neu/*.req
```

Nachgemessen am 27.9.2026 (1.1.6 von PyPI gegen 1.2.0): genau zwei Änderungen
— `fastmcp` entfernt (im CHANGELOG) und `mcp[cli]` → `mcp` (nicht darin). Die
neun übrigen Commits erscheinen nicht. Ohne `grep -v 'extra =='` wären es acht
Zeilen statt drei, fast alle aus dem `dev`-Extra: Der Filter trennt Nutzer- von
Entwicklerseite. Gegenprobe: dasselbe Wheel gegen sich selbst ergibt Exit 0.

Jede Zeile des Diffs braucht einen CHANGELOG-Eintrag. Was er nicht zeigt, deckt
er nicht ab — Verhaltensänderungen im Code stehen nie in `Requires-Dist`, dafür
bleibt `git log -- src/`.

### Der Vertrag mit swissreg.ch

Am 4.10.2026 liefen die Live-Tests erstmals mit echten Zugangsdaten, und es
zeigte sich: **Der Server hatte die Quelle nie getroffen** — auf beiden Seiten,
Antwort und Anfrage. Was jetzt gilt, ist gemessen und in
`tests/fixtures/live/` aufgezeichnet.

| Antwort (WIPO ST.96) | Wo |
|---|---|
| ein Datensatz | direktes Kind von `Result` mit `role="item"` — Marken `Data`, Patente und SPC `DataBag` |
| Gesamttreffer | `Meta/TotalItemCount` (dazu `ItemCount`, `ItemCountOffset`) |
| Folgeseiten-Token | **Textinhalt** von `Continuations/Continuation` |
| Absage der Quelle | `Result/@success="false"` plus `Log/LogEntry` — bei HTTP **200** |

| Anfrage | Form |
|---|---|
| Folgeseite | `Continuation` als **Action** in der nächsten `ApiRequest` (sie gehört zur `AbstractAction`-Gruppe), nicht `<Page token="…">` |
| exakte Nummernsuche | `<ns:ApplicationNumber>` im **Register**-Namespace (`tm:`/`pat:`/`spc:`), Nummer als Text |
| Publikationssuche | Request-Element in `datadeliverypatentpublication-1.0.0` |

**Was es nicht gibt:** `Item`, `Meta/TotalCount`, `<Id>` als Feld für
Registerdaten, `RegistrationNumber` oder `ApplicationNumberText` als
Abfragefeld. Eine Marke ist nicht über ihre Registernummer nachschlagbar.

Die Rechnung: Jede Antwort kam als `count: 0, total: null` an, auch die mit
drei Sätzen und 201798 Treffern. Seite 2 war immer Seite 1.
`swiss_ip_search_patent_publications` bekam seit je `could not parse the action
PatentPublicationSearch` und gab das als «nichts gefunden» weiter — 39578
Treffer für `Roche*`, die niemand sah.

Fünf Handgriffe daraus:

- **Satzgrenze ist, was die Quelle markiert, nicht was der Payload heisst.**
  `BibliographicData` kommt in einer Patent-Antwort 4× bei 3 Sätzen vor, eines
  verschachtelt unter `PatentPublication`. `role="item"` schliesst nebenbei
  die Kontingent-Antwort (`role="quota"`) von selbst aus.
- **Ein `success="false"` ist kein leeres Ergebnis.** `raise_for_status()` ist
  mit HTTP 200 zufrieden, und wer nur Sätze zählt, meldet null. Der
  403-Absatz aus Teil 1, eine Ebene tiefer: Nicht der Statuscode entscheidet,
  sondern ob die Quelle die Frage beantwortet hat.
- **Die Fehlermeldung ist eine Auskunft.** Auf `<ApplicationNumber>` im
  common-Namespace antwortet die Quelle `Maybe misspelled? -
  {…datadeliverytrademark-1.0.0}ApplicationNumber` — sie nennt die Lösung
  selbst. Unbekannte Action-Namen geben `unsupported action type`,
  `PatentPublicationSearch` dagegen `could not parse the action`: Name richtig,
  Rumpf falsch. Beides sieht nur, wer den Wortlaut mitführt statt bloss
  `success`.
- **Die Stille ist auch eine Auskunft — aber nur neben einer Kontrolle.** Zu
  `ApplicationNumberText` und `RegistrationNumber` schwieg die Quelle, während
  sie bei `ApplicationNumber` half: Die beiden existieren nicht. Dasselbe bei
  den Action-Namen, wo drei erfundene als Nulllinie mitliefen — sonst wären es
  vier gleich aussehende Fehlschläge gewesen und das Raten wäre weitergegangen.
- **Was gefunden wird, ist nicht, was gesucht war.** `<Any>` mit einer Nummer
  liefert Treffer (397 bzw. 2), aber als Volltext über alle Felder. Als Ersatz
  für eine exakte Nummernsuche eine stille Ungenauigkeit.

**Warum kein Test das sehen konnte**, ist die eigentliche Lektion: Die
handgeschriebenen Fixtures nannten dieselben falschen Namen wie
`_parse_result_page`. 171 grüne Unit-Tests, und die einzige Zusicherung gegen
die echte Quelle —
`assert result["count"] > 0` — war die, die fiel. Der Mechanismus, vor dem
Teil 1 unter «Tests» warnt, hier als Rechnung statt als Warnung.

Messläufe: 37198882345, 37198983962 (Antwortform), 37204457180 (Pagination,
Rumpf), 37204541287 (Nummernfeld), 37204640122 (Patente, SPC).

### Aufzeichnungen und Messsonden

`tests/fixtures/live/` hält echte Antworten: Form echt, Textwerte synthetisch,
Aufnahmedatum in `RECORDING.md`. Echt bleiben Elementnamen, Namespaces,
Verschachtelung, Anzahl, Attribute, die `Meta`-Zähler (sie müssen zur Satzzahl
passen) und die `LogEntry`-Meldungen (sie betreffen die eigene Anfrage). Die
Dateien belegen die **Form**, nicht den Inhalt: Ein Test darf daraus ableiten,
wie die Felder heissen, nicht wie ein Datensatz aussieht.

Zwei Kopplungen halten das zusammen, beide Lehren aus Fehlern:

- **Ein handgeschriebenes Beispiel wird gegen die Aufzeichnung gehalten, nicht
  statt ihr.** `TestBeispieleStimmenMitDerAufzeichnung` fällt, wenn beide
  auseinandergehen; ohne diese Kopplung ist das Beispiel wieder nur die Annahme
  seines Autors.
- **Was synthetisch aussieht, beschreibt eine Stelle.** Der Rekorder sagt es
  (`ist_synthetisch`), die Zusicherung im Repo fragt ihn. Zwei Beschreibungen
  desselben Musters gehen auseinander — am 4.10.2026 galt `MUST`, ein
  abgeschnittenes `MUSTER`, als Registerinhalt.

**Messen geht von Hand.** Drei Sonden, alle über `shape-probe.yml` per
`workflow_dispatch`:

| Modus | Skript | Ausgabe |
|---|---|---|
| `messen` | `scripts/probe_response_shape.py` | Form einer Antwort (Pfade, Attributnamen, Textlängen) ins Log |
| `aufzeichnen` | `scripts/record_live_fixtures.py` | Fixtures als Artifact, Selbstkontrolle vor dem Schreiben |
| `anfrageformen` | `scripts/probe_request_forms.py` | Id-Formen, Pagination, Action-Rumpf — je mit Nulllinie |

Ein **neuer** Workflow ist erst dispatchbar, wenn seine Datei auf dem
Default-Branch liegt (sonst `404`); die **Inputs** werden gegen die Fassung des
`ref` geprüft, dort lässt sich also auf einem Branch iterieren.

**Eine Messsonde ist Code wie jeder andere.** Die Sonde fiel am 4.10.2026 in
der CI an einer eigenen Liste von Tupeln verschiedener Länge (Lauf
37204275286) — zwei Minuten Wartezeit und ein Lauf mit Zugangsdaten für etwas,
das jeder Aufruf ohne Netz gezeigt hätte. Was ohne Quelle prüfbar ist, steht in
`tests/test_probe_request_forms.py`.

**Kandidaten aus einem echten Satz ableiten, nicht erfinden.** Wer eine Nummer
erfindet, misst nicht das Format, sondern nur, dass die Nummer nicht existiert.

### Die Live-Suite und ihr Melder

`.github/workflows/live.yml`, `cron: "0 3 * * 1"` plus `workflow_dispatch`.
`schedule` greift nur auf dem Default-Branch (hier `main`): Änderungen wirken
erst nach dem Merge, vorher von Hand.

**Seit dem 4.10.2026 sind `IGE_USERNAME` und `IGE_PASSWORD` gesetzt und der
Lauf ist `clear`** — 4 von 4 Tests ausgeführt, nicht übersprungen (Lauf
37209564726). Der erste Lauf, der überhaupt etwas über den Vertrag mit der
Quelle festgestellt hat; das zugehörige Issue hat der Workflow selbst
geschlossen.

**Vorher war er rot, und das war die richtige Antwort.** Ohne Zugangsdaten
überspringt jeder Live-Test (`skipif(not LIVE)`), und bis zum 24.8.2026
meldete der Job dafür Erfolg — zehn grüne Wochenläufe, in denen nichts geprüft
wurde; seit `ab38c24` war er rot. Wer die Fehlermeldung eines solchen Jobs für
den Fehler hält und `live.yml` daraufhin repariert, repariert den Melder.

Der Melder brauchte vier Fassungen, jede Korrektur eine eigene Lektion:

- **Ein halb gesetztes Secret ist schlimmer als gar keines.** Die Schranke im
  Workflow und die Marke in `tests/test_server.py` fragten allein nach
  `IGE_USERNAME`, `_load_credentials` verlangt beides. Mit halben Zugangsdaten
  fallen die Live-Tests geschlossen an einem
  `ToolError`, die Einordnung meldet `finding` — ein Issue, das swissreg.ch
  einen Vertragsbruch unterstellt wegen eines fehlenden Secrets. Der richtige
  Befund ist `unknown`.
- **Ein geliehener Exit-Code ist kein Grund.** Der Nicht-Lauf reichte
  `--pytest-exit 127` durch; die Einordnung machte daraus «pytest ist nicht bis
  zum Schreiben gekommen (Exit 127)», also «command not found», also die Suche
  nach einem fehlenden Binary. Wer einen Zustand meldet, den er selbst
  herbeigeführt hat, benennt ihn — dafür gibt es `--not-started`.
- **Die Meldung muss den Unterschied halten, von dem sie lebt.** Fassung zwei
  sagte «Unvollständige IGE-Zugangsdaten» auch dann, wenn gar nichts gesetzt
  war. Wer «unvollständig» liest, sucht die zweite Hälfte eines Secrets, das
  nie eine erste hatte.
- **Der Melder kann sich selbst überschreiben.** Die pytest-Ausgabe ging über
  einen Heredoc mit festem Trennwort `PYTEST_TAIL` in `$GITHUB_OUTPUT` —
  dieselbe Datei, in die `classify_live_run.py` `state=` schreibt. Steht
  `PYTEST_TAIL` in der Ausgabe, endet der Block dort und der Rest wird als
  Output gelesen. Nachgestellt am 8.9.2026: aus `state=unknown` wurde
  `state=clear`, der rote Lauf wäre grün geworden und hätte das Issue
  geschlossen. Das Trennwort wird je Lauf zufällig gezogen.

**Und die Suite selbst war kaputt, nicht nur ihr Melder.** `_client` ist ein
Modul-Global; eine gepoolte Verbindung gehört aber der Loop, die sie geöffnet
hat, und `pytest-asyncio` gibt jedem Test eine eigene. Zwei der vier Live-Tests
fielen an `RuntimeError: Event loop is closed` — rot, rot, grün, rot, weil der
Pool zwischendurch neu aufbaut. Die Klasse läuft jetzt in einer Loop
(`loop_scope="class"`), wie im Betrieb, wo `_lifespan` eine Loop für den
Prozess besitzt. Den Client je Test wegzuwerfen hätte je Test ein neues Token
geholt, wovon die API-Doku abrät.
