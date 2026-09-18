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
  als Entwarnung für die gesperrte nehmen. Das ist dieselbe Asymmetrie wie
  bei der verschwundenen Codex-Meldung weiter unten.

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

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Wie lange die Sperre dauerte, geben die Beobachtungen nur als Spanne her. Vier
Zeitpunkte sind belegt: letzter gelungener Review am 21.8. um 08:41, erste
Limit-Meldung um 09:48, letzte Limit-Meldung *jener Episode* am 22.8. um 11:03,
erste *andere* Meldung am 23.8. um 08:22. (Am 29.8. kam wieder eine — die
gehört zu einer anderen Episode und steht weiter unten.)

Zwischen erster und letzter Limit-Meldung liegen **25 h 15 min**. Das ist der
Abstand zweier Fehlschläge, nicht die Dauer einer Sperre. Wer ihn Untergrenze
nennt, hat die durchgehende Erschöpfung schon vorausgesetzt, die er belegen
soll: Öffnete sich das Fenster zwischendurch und schloss es sich durch neue
Auslöser wieder, waren es zwei kurze Sperren und nie eine von 25 Stunden.
Untergrenze einer *einzelnen* Sperre sind die 25 h 15 min nur unter genau dieser
Annahme — und die ist unbelegt.

Nach oben trägt die Rechnung dagegen. Die längste mit den Beobachtungen
verträgliche Sperre reicht vom letzten Erfolg um 08:41 bis zur abweichenden
Meldung um 08:22, also **47 h 41 min**; länger kann keine einzelne gewesen sein.
Wer stattdessen ab der ersten Limit-Meldung rechnet, unterschlägt die 67
Minuten, in denen das Kontingent schon weg gewesen sein kann, und nennt die
Spanne zwischen zwei Beobachtungen eine Obergrenze.

Beobachtungspunkte sind keine Messreihe — die 21 Stunden vor der abweichenden
Meldung liefen ganz ohne Codex-Auslöser, dort hat niemand gemessen.

In der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden,
ohne dass jemand hineingesehen hat, und am 22.8. noch einmal 43.

**Vier** Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann schreibt er einen gewöhnlichen Issue-Kommentar:

  ```
  Codex Review: Didn't find any major issues. Swish!
  ```

  Der Schlusssatz wechselt bei jedem Lauf («Delightful!», «Keep it up!»,
  «More of your lovely PRs please.»); stabil ist nur der Satz davor. Der
  Infokasten, den Codex unter jeden Review setzt, behauptet weiterhin eine
  Reaktion («otherwise it will react with 👍») — am 23.8. kam in sechs Repos
  die Meldung und in keinem die Reaktion. Der Kasten ist keine Quelle.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Für das Repo fehlt eine Environment** — dann schreibt er:

  ```
  To use Codex here, create an environment for this repo.
  ```

Der vierte kam erst zum Vorschein, als der dritte wegfiel, und das ist kein
Zufall: Die Prüfungen liegen hintereinander. Dass es diese Reihenfolge ist und
nicht die umgekehrte, lässt sich an einem einzigen Repo ablesen — in
`swiss-public-data-mcp` bekam PR #54 am 22.8. um 10:56:55 die Kontingent-Meldung
und PR #56 am 23.8. um 08:22:20 die Environment-Meldung. Läge die
Environment-Prüfung vorn, hätte #54 sie schon am Vortag gesehen; die Environment
fehlte ja bereits. Zwei Meldungen aus demselben Repo schlagen hier jede
Vermutung über die Reihenfolge.

Praktisch heisst das: **Eine verschwundene Limit-Meldung ist keine Entwarnung.**
Sie kann bedeuten, dass das Kontingent wieder da ist — und dass jetzt etwas
anderes den Review verhindert. Belegt ist eine Prüfung erst durch ein
Review-Objekt **oder** eine Befundlos-Meldung. Wer nur das Objekt gelten lässt,
zählt jeden befundlosen Review als ungeprüft — und baut sich denselben Fehlalarm
ein, den dieser Abschnitt verhindern soll, nur in die andere Richtung.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein Review **mit** Befund ist ein Review-Objekt
(«💡 Codex Review», mit Commit-Angabe); ein Review **ohne** Befund und die
beiden Ausfallmeldungen — Kontingent wie Environment — sind gewöhnliche
Issue-Kommentare und trennen sich nur im Text. Beim Draft gibt es überhaupt
nichts, weil Codex nicht anläuft; ein kommentarloser Draft ist deshalb kein
Beleg, sondern ein nicht durchgeführter Test.

Das sind verschiedene Abfragen — `get_reviews` fürs Objekt, `get_comments` für
alles andere; wer nur eine nimmt, übersieht den Rest. Genau so ist die
Limit-Meldung zuerst durchgerutscht.

Der Kommentarzähler allein reicht ohnehin nicht: `comments: 1` kann die
Befundlos-, die Kontingent- **oder** die Environment-Meldung sein — drei
gegensätzliche Bedeutungen unter derselben Zahl. Den Text lesen, nicht die Zahl.
Und einen unbekannten vierten Text wörtlich zitieren, statt ihn in eine der
bekannten Schubladen zu zwingen: Dieser Abschnitt musste schon einmal von drei
auf vier Gründe wachsen, und die 👍-Reaktion stand hier zwei Fassungen lang als
Tatsache.

**Seit dem 8.9.2026 gibt es eine fünfte Form, und sie ändert ihren Sinn im
Lauf.** Codex setzt einen Statuskommentar «Codex Review Summary» mit einer
Tabelle aus Review, Status, Commit und Auslöser. Auf PR #73 stand dort um
04:13:04 `🔄 Running` und um 04:14:23 `✅ Completed` — **derselbe Kommentar**,
bloss bearbeitet: eine `id`, `created_at` fest, `updated_at` nachgezogen. Der
Zähler bleibt bei `comments: 1`, und diesmal reicht auch der Text nicht: Er ist
eine Momentaufnahme, kein Befund. Wer ihn im Moment eines schnellen Merges
liest, liest `Running` — und das heisst gar nichts.

Für die Frage, **ob** geprüft wurde, ist die Tabelle trotzdem ein dritter
Beleg neben Review-Objekt und Befundlos-Meldung: Sie nennt Commit und
Abschlusszeit.
Für die Frage, **wie** es ausging, ist sie keiner. `Completed` ohne
Befundlos-Meldung sagt, dass ein Lauf zu Ende kam, nicht dass er nichts fand.

Der Infokasten nennt inzwischen zwei Reaktionen — 👀 während des Laufs, 👍 am
befundlosen Ende. Auf #73 kam **keine von beiden** (`reactions: 0`), bei einem
Lauf, der laut derselben Tabelle sauber durchgelaufen ist. Der Kasten war schon
zweimal keine Quelle und ist es weiterhin nicht; dass er jetzt zwei
Behauptungen trägt statt einer, macht ihn nicht besser.

Und ein befundloser Lauf ist kein Freispruch. Am 23.8. lief derselbe Text durch
42 Reviews: 36 meldeten denselben P2-Befund, 6 die Befundlos-Meldung — gleiche
Eingabe, gegenteiliges Urteil, alles in denselben neun Minuten. Ein sauberer
Lauf sagt damit etwas über den Lauf, nicht über den Text. Wer sein Häkchen
daran hängt, hängt es an einen Münzwurf.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Am 29.8.2026 traf beides denselben PR. In `swiss-ip-mcp` ging PR #61 um
09:28:20 von Draft auf ready und war um 09:28:24 gemergt — vier Sekunden, genau
das Muster oben. Die Kontingent-Meldung kam um 09:28:25, eine Sekunde nach dem
Merge.

Sie entlastet die vier Sekunden nicht. Belegt ist nur, dass die
*Kontingent-Prüfung* fünf Sekunden nach dem Auslöser fertig ist; eine Absage
ist billiger als ein Review, und wie lange ein wirklicher Review braucht, sagt
sie nicht. Hier ist der Prüfer nur schon vorher an etwas anderem gescheitert.
Wer zwei Gründe hat und einen abstellt, hat den Review noch nicht.

**Am 8.9.2026 ist es gemessen.** Wieder in `swiss-ip-mcp`, wieder wenige
Sekunden zwischen Freigabe und Merge: PR #73. Diesmal war das Kontingent da,
und der Prüfer lief wirklich an.

```
04:12:52/53  Draft → ready (der Auslöser)
04:12:56     Merge            (merged_at)
04:13:00.98  Codex startet den Review auf 8aff614
04:14:22.39  Codex meldet «Completed»
```

Der Review begann **fünf Sekunden nach dem Merge** und war **86 Sekunden**
danach fertig; er selbst lief 81 Sekunden. Damit ist die Frage des Absatzes
darüber für einen Fall beantwortet, und nur für den: ein Diff über zwei
Dateien, 60 Zeilen zu 7. Ein grösserer braucht eher mehr. Wer daraus eine
Wartezeit ableitet, hat aus einer Messung eine Regel gemacht; sie ist die
Untergrenze für diesen einen PR, sonst nichts.

**Die Uhr, an der man das abliest, muss die richtige sein.** Die Freigabezeit
oben trägt bewusst einen Schrägstrich: Sie stammt aus der Zustellung eines
Webhook-Ereignisses, und dieselbe Zustellung datierte den Merge auf 04:12:57,
während GitHubs eigenes `merged_at` 04:12:56 sagt — eine Sekunde daneben. Bei
Abständen von drei, vier Sekunden entscheidet das über die Aussage. Die
Codex-Zeiten und `merged_at` kommen aus der API, die Freigabe nicht; deshalb
steht hier keine glatte Zahl für «ready bis Merge», sondern drei bis vier
Sekunden.

Für die älteren Sekundenangaben in diesem Abschnitt — die vier Sekunden am
21./22.8., die vier bei #61 — ist das nicht nachgeholt: `merged_at` kommt in
diesem Abschnitt erst hier vor. Sie bleiben stehen, weil die Aussage «zu
schnell gemergt» eine Sekunde hin oder her nicht trägt; wer sie aber gegen 86
Sekunden rechnen will, prüft sie vorher gegen die API.

Verloren ging hier kein Befund — der Review postete keinen. Verloren ging das
Gate: Gemergt wurde, bevor feststand, ob es einen gibt. Das ist der Unterschied,
den die Checkliste im PR-Template nicht sieht; sie war formal abgehakt. Und ob
ein Review auf einem schon geschlossenen PR derselbe ist wie auf einem offenen,
prüft dieser Lauf nicht mit — er meldete `Completed`, mehr steht nicht fest.

**Keine zwanzig Minuten später dasselbe, auf dem PR, der genau das
festhielt.** #74 trug diesen Abschnitt nach und ging denselben Weg:

```
04:31:19     Draft → ready (Zustellzeit, siehe oben)
04:31:22     Merge            (merged_at)
04:31:30.46  Codex startet den Review auf 1ace034
04:32:51.75  Codex meldet «Completed»
```

Nebeneinander:

```
      Merge→Start   Laufzeit   Merge→fertig
#73      5.0 s       81.4 s       86.4 s
#74      8.5 s       81.3 s       89.7 s
```

**Der nächste Absatz ist am Tag darauf überholt worden — die dritte Messung
weiter unten hat ihn umgestossen.** Er bleibt trotzdem stehen: Wie die Vermutung
entstand und woran sie zerbrach, ist hier der Lehrsatz, nicht die Vermutung.

Der Vorlauf unterscheidet sich um dreieinhalb Sekunden, die Laufzeit auf die
Zehntelsekunde nicht. Das sieht nach festem Zeitbudget aus statt nach Arbeit,
die mit dem Umfang wächst — belegt ist es nicht: Beide Diffs sind gleich gross
(60 Zeilen zu 7 in zwei Dateien, 60 zu 0 in einer). Zwei Messungen derselben
Grössenordnung können nicht unterscheiden, ob die Zeit am Umfang hängt.
Entscheiden würde ein Diff anderer Grössenordnung; bis dahin bleibt «ein
grösserer braucht eher mehr» eine Vermutung und keine Messung — auch nachdem
jetzt zweimal gemessen wurde.

Was die zweite Messung trägt, ist das Muster: Zweimal begann der Prüfer **nach**
dem Merge, nie davor. Und beide Male postete er nichts — kein Review-Objekt,
keine Befundlos-Meldung, `reactions: 0`. Der Infokasten verspricht damit ein
drittes Mal eine Reaktion, die nicht kommt.

**Die Startzeit ist nur im Lauf ablesbar.** Beide `Merge→Start`-Werte stammen
aus einer Abfrage, die den Statuskommentar traf, solange er noch «Running
since …» zeigte. Er wird an Ort und Stelle bearbeitet, und der fertige Text
nennt allein die Abschlusszeit: Die Startzeit ist überschrieben und aus der API
nicht mehr zu holen. Die fünfte Form ändert also nicht bloss ihren Sinn im Lauf,
sie löscht die frühere Lesung. Wer den Vorlauf messen will, muss hinsehen,
während der Review läuft.

**Und genau das hat die dritte Messung am 9.9.2026 möglich gemacht — die dann
die zweite umgestossen hat.** #75 trug den Vorbehalt oben nach und wurde
wieder nach wenigen Sekunden gemergt; diesmal wurde der Statuskommentar
abgefragt, solange er noch lief, und die Startzeit war da:

```
03:13:56     Draft → ready (Zustellzeit)
03:14:01     Merge            (merged_at)
03:14:03.28  Codex startet den Review auf 70e8ad3
03:15:40.95  Codex meldet «Completed»
```

Alle drei nebeneinander, mit dem Umfang des jeweiligen Diffs:

```
      Diff              Merge→Start   Laufzeit   Merge→fertig
#73   2 Dateien, 60/7      5.0 s       81.4 s       86.4 s
#74   1 Datei,   60/0      8.5 s       81.3 s       89.7 s
#75   1 Datei,   40/0      2.3 s       97.7 s       99.9 s
```

**Das feste Zeitbudget ist damit weg.** Zwei gleiche Laufzeiten waren eine
Koinzidenz, keine Konstante; die dritte liegt 16 Sekunden darüber. Und der
Verdacht kippt gleich doppelt: Der **kleinste** Diff der drei brauchte am
längsten. Damit ist auch «ein grösserer braucht eher mehr» in dieser
Grössenordnung nicht bloss unbelegt, sondern widerlegt — was ein wirklich
grosser Diff tut, ist weiter offen, und dieser Satz beansprucht nicht mehr als
das. Der Vorlauf streut über den Faktor vier (2,3 bis 8,5 Sekunden) und war nie
das Stabile daran.

Der Reihe nach: Eine Messung liess die Frage offen, zwei erzeugten ein Muster,
drei haben es zerlegt. Wer nach der zweiten aufgehört und «festes Budget»
notiert hätte, stünde jetzt mit einem falschen Satz da — die Vorsicht im
Absatz darüber war kein Zierrat.

Was drei Messungen stützen, ist einzig das Muster, um das es hier geht: **Der
Prüfer begann dreimal nach dem Merge, nie davor.** Und dreimal postete er
nichts — kein Review-Objekt, keine Befundlos-Meldung, `reactions: 0`. Die
Reaktion, die der Infokasten verspricht, fehlt damit zum vierten Mal.

**Die vierte Messung am 18.9.2026 nimmt die Verallgemeinerung aus diesem Satz
zurück — und den Verdacht über den Umfang wieder auf.** Der Satz selbst bleibt
wahr: jene drei Läufe begannen nach dem Merge. Falsch wäre nur, daraus etwas
über den Prüfer zu lesen, und genau das legt er nahe. #77 in `swiss-ip-mcp`
war der Diff anderer Grössenordnung, den der Absatz oben als offen benennt:
acht Dateien, 514 Zeilen zu 24, gegen 60/7, 60/0 und 40/0 bei den drei davor.
Und er wurde **nicht** sofort gemergt.

```
10:35:32     Draft → ready (Zustellzeit)
10:35:42.87  Codex startet den Review auf e9bb37f
10:38:17.27  Codex meldet «Completed»
10:39:45     Merge            (merged_at)
```

Die Laufzeit ist die einzige Grösse, die über alle vier sauber definiert ist —
sie steht bei jeder in Codex' eigenen Zeitstempeln. «Merge→Start» gibt es hier
nicht, weil der Merge danach kam; die Tabelle oben bleibt deshalb stehen, wie
sie ist, statt eine Spalte zu bekommen, die für eine Zeile keinen Wert hat:

```
      Diff                  Laufzeit
#73   2 Dateien,  60/7        81.4 s
#74   1 Datei,    60/0        81.3 s
#75   1 Datei,    40/0        97.7 s
#77   8 Dateien, 514/24      154.4 s
```

**Was sie nicht hergibt: die Ursache.** Gegenüber den drei davor sind ZWEI
Dinge anders — der Umfang und der Umstand, dass kein Merge vorausging. Welches
von beiden die 154 Sekunden macht, trennt diese Messung nicht, und «ein
grösserer braucht eher mehr» ist damit wieder eine Vermutung, nicht mehr eine
widerlegte. Nach der Lehre des Absatzes darüber — zwei Werte ergaben ein
Muster, das der dritte zerlegte — wäre es genau der Fehler, aus der vierten
jetzt eine Regel zu machen. Zwei Variablen auf einmal zu bewegen war
unvermeidlich: Der PR wurde gemergt, als er fertig war, nicht als ein Versuch
es verlangte.

**Der Prüfer begann diesmal vor dem Merge und war vor ihm fertig** — 87,7
Sekunden vor ihm. Damit ist klar, was das Muster «dreimal nach dem Merge» in
Wahrheit war: keine Eigenschaft des Prüfers, sondern der Schatten des
Mergens nach drei bis fünf Sekunden. Sobald nicht sofort gemergt wird, steht
der Befund vor dem Merge fest. Der Abschnitt dokumentiert also nicht, dass
Codex spät kommt, sondern dass hier zu früh gemergt wurde — und das ist der
Satz, um den es die ganze Zeit ging.

Verloren ging diesmal nichts. Das Gate hielt: Beim Merge stand fest, dass es
keinen Befund gibt.

**Aber «kein Befund» ist auch hier nicht «geprüft und sauber».** Abgefragt
wurden beide Seiten — `get_reviews` kam leer zurück, unter den Kommentaren
stand allein die Statustabelle. Es fehlt also auch die Befundlos-Meldung, und
damit gilt weiter, was oben steht: `Completed` belegt, **dass** ein Lauf zu
Ende kam, nicht **dass** er nichts fand. `reactions: 0` zum vierten Mal in
Folge; die Reaktion, die der Infokasten verspricht, fehlt damit zum fünften
Mal insgesamt.

Zwei Handgriffe aus dem Absatz darüber haben sich bezahlt gemacht. Die
Startzeit war da, weil während des Laufs nachgesehen wurde — eine Abfrage
nach dem Abschluss hätte nur noch die Abschlusszeit gezeigt. Und die
Mergezeit wurde aus der API nachgeholt statt aus der Zustellung genommen: die
Webhook-Zustellung des `closed`-Ereignisses nannte 10:39:46, `merged_at` sagt
10:39:45. Wieder eine Sekunde, wieder in dieselbe Richtung.

**Und das Kontingent kommt wieder — und geht wieder.** Zwischen der letzten
Meldung vom 22.8. und dieser vom 29.8. liegt die Environment-Meldung vom 23.8.
um 08:22, und die belegt nach der Reihenfolge oben, dass das Kontingent an
jenem Morgen da war: Die Environment-Prüfung kommt erst dran, wenn die
Kontingent-Prüfung durch ist. Es waren also mindestens zwei getrennte Episoden
und nicht eine durchgehende Sperre seit dem 21.8.

Über die Dauer der neuen sagt das nichts. Drei PRs desselben Vormittags — #61,
#62 und #63 — bekamen der Reihe nach dieselbe Meldung, die letzte um 09:37:53,
und jeder Merge lag drei bis vier Sekunden nach «ready for review».

Wie viele es an jenem Vormittag insgesamt waren, steht hier bewusst nicht. Jeder
PR, der die Zahl nachträgt, löst beim Umschalten auf ready den nächsten
Codex-Lauf aus und erzeugt damit die nächste Meldung: Der Satz ist überholt,
bevor sein eigener Merge durch ist. Zweimal so geschehen — «eine einzige
Beobachtung» hielt fünf Minuten, «zwei Fehlschläge» keine zwei. Eine Zahl, die
sich beim Aufschreiben ändert, gehört nicht in einen Satz, der etwas belegen
soll.

Belegt ist, dass die Episode um 09:37 noch lief — kein Anfang, kein Ende, und
welches Limit greift, bleibt offen wie zuvor. Und: Ein Repo, in dem Codex
gestern durchlief, ist kein Beleg für heute; ein Vormittag keiner für den
Nachmittag.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Welches hier griff, ist **offen**. Die Lücke oben
schliesst das Fünf-Stunden-Fenster nicht aus: Es kann sich zwischendurch
geöffnet und durch neue Auslöser wieder erschöpft haben. Das auszuschliessen
bräuchte den Nachweis, dass in der ganzen Spanne kein einziger Review durchlief
— den gibt es nicht, weil nur Fehlschläge beobachtet wurden. Eine lange Reihe
von Fehlschlägen belegt eine lange Reihe von Fehlschlägen, nicht ihre Ursache.

Zeigt das Dashboard freies Kontingent, während Reviews weiter scheitern, ist
das ein bekannter Fehler bei mehreren verbundenen Konten — dann den
GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

Die Environment legt man unter `chatgpt.com/codex/cloud/settings/environments`
an, und zwar **je Repo**. Die Meldung sagt es selbst («for this repo»), und am
23.8. war es genau so: In `swiss-public-data-mcp` fehlte sie, dort kam kein
Review; in den übrigen Repos lief Codex am selben Morgen durch. Eine
Environment fürs Konto genügt also nicht — wer eine anlegt und den Rest für
erledigt hält, mergt weiter Ungeprüftes.

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
