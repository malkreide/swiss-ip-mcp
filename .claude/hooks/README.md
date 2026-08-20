# SessionStart-Hook: Klon-Aktualität

`check-clone-freshness.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<default-branch>` liegt.

## Grund

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache **nicht im Diff stand** — die fehlenden Commits waren jeweils genau
die, die das Gate einführten, an dem der Branch scheiterte. Die Prüfung kostet
eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.

Der Reason steht hier und im Skript-Kopf, nicht in `settings.json`: JSON kennt
keine Kommentare, und ein `_comment`-Schlüssel wäre eine zweite Quelle, die
irgendwann von dieser abweicht.

## Zusicherungen, in dieser Reihenfolge

1. **Der Hook blockiert die Session nie.** Kein Netz, kein `origin`, detached
   HEAD, flatterndes DNS, fehlendes `git`, leeres Repo, Credential-Prompt —
   jeder dieser Fälle endet still mit Exit 0. Ein Hook, der bei Netzproblemen
   die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und schützt
   danach gar nichts.
2. **Kurzes Timeout.** 3 s auf `ls-remote`, 4 s auf `fetch`
   (`CLONE_FRESHNESS_LS_TIMEOUT` / `CLONE_FRESHNESS_FETCH_TIMEOUT`).
   `settings.json` setzt zusätzlich `"timeout": 15` als zweite, unabhängige
   Schranke — fällt die eine aus, greift die andere.
3. **Ausgabe nur, wenn Commits fehlen.** Bei 0 schweigt er.
4. **Der Default-Branch wird ermittelt, nicht angenommen.** Im Portfolio
   heissen `openlex-mcp`, `swiss-courts-mcp` und `swisstopo-mcp` ihren
   Default-Branch `master`; die `main`-Annahme hat dort schon einmal einen
   Branch 15 Commits alt werden lassen.

## Warum `ls-remote --symref` und nicht `refs/remotes/origin/HEAD`

Der lokale Ref wäre gratis, taugt aber nicht als Quelle:

- In frisch geklonten CI- und Web-Containern **fehlt er** — in genau diesem
  Repo liefert `git symbolic-ref refs/remotes/origin/HEAD` rc=1. Der Hook
  wäre dort dauerhaft still, ohne dass etwas widerspricht.
- Nach einer Branch-Umbenennung zeigt er weiter auf den alten Namen.

Beides sind stille Ausfälle einer Schutzmassnahme — die Bauart, vor der
`CLAUDE.md` warnt. Der Netzaufruf ist ohnehin nötig, der zusätzliche
Round-Trip kostet ~0.3 s.

## Kein `matcher`

`SessionStart` feuert mit `startup`, `resume`, `clear`, `compact`. Ein
`matcher: "startup|resume"` würde bei abweichender Matcher-Semantik dazu
führen, dass der Hook **nie** läuft — wieder ein stiller Ausfall. Ohne
Matcher läuft er auf allen Quellen; der Preis ist ein zusätzlicher
Sub-Sekunden-Fetch nach `/compact`, und eine Wiederholung der Meldung genau
dann, wenn der Klon tatsächlich noch veraltet ist.

## Nicht auf `CLAUDE_CODE_REMOTE` eingeschränkt

Die Skill-Vorlage schränkt Hooks auf die Web-Umgebung ein. Hier wäre das
verkehrt herum: Web-Container klonen frisch, veraltete Klone sind das lokale
Problem. Der Hook läuft überall.

## Tests

```bash
.claude/hooks/test-check-clone-freshness.sh              # 12 Faelle
.claude/hooks/test-check-clone-freshness.sh --gegenprobe # 6 Mutationen, ~60 s
```

Die Tests bauen echte Repos mit lokalem `origin` — keine handgeschriebenen
Fixtures, die nur die Annahme des Autors zurückspielen. Abgedeckt: beide
Richtungen (veraltet → Meldung, aktuell → Schweigen), die `master`-Erkennung,
eigene Commits ohne Rückstand, detached HEAD, fehlendes `origin`, kein
git-Repo, fehlendes Verzeichnis, Repo ohne Commit, nicht auflösbares Remote,
gescheiterter fetch bei lesbaren Refs, und ein garantiert hängendes Remote
(`ext::sleep 30`) gegen die Timeout-Schranke. Jeder Fall prüft zusätzlich
Exit 0 und leeres stderr.

Die Gegenprobe nach `CLAUDE.md` entfernt jede Zusicherung einzeln und zeigt,
dass genau die zugehörigen Fälle fallen. Die Mutation ist per `assert`
verankert: eine Mutation, die still nicht greift, würde eine bestandene
Gegenprobe vortäuschen.

Zwei Befunde aus der Gegenprobe, die im Code stehen bleiben sollten:

- Der ursprüngliche Testsatz erreichte den `fetch` in keinem Fehlerfall — DNS-
  und Hänger-Fall brechen schon beim `ls-remote` ab. Das `|| exit 0` am fetch
  war damit unbelegt. Dafür gibt es jetzt den Fall «fetch scheitert (origin
  defekt)»: Refs lesbar, Objekte weg.
- «fetch-Exitcode ignorieren» ist für sich **nicht** widerlegbar: git kürzt
  `FETCH_HEAD` beim Start jedes fetch, ein veralteter Wert bleibt also nicht
  liegen (geprüft mit git 2.43). Der Zahlenwächter
  (`case "$behind" in ''|*[!0-9]*)`) fängt den dann leeren Wert ab; widerlegbar
  wird beides erst gemeinsam.

## Lauf gegen das echte Remote

| Lage | Ergebnis |
| --- | --- |
| Klon aktuell | still, Exit 0, 1 s |
| 3 Merge-Commits zurück | `'…' liegt 6 Commits hinter origin/main`, Exit 0, 1 s |

Die 6 ist korrekt: `HEAD~3` folgt drei Merge-Commits über den First-Parent, es
fehlen tatsächlich sechs Commits.
