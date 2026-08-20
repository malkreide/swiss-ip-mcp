#!/usr/bin/env bash
#
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<default-branch> liegt.
#
# GRUND
#   Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
#   Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau
#   die, die das Gate einfuehrten, an dem der Branch scheiterte. Die Pruefung
#   kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# OBERSTE REGEL: DIESER HOOK BLOCKIERT DIE SESSION NIE.
#   Kein Netz, kein origin, detached HEAD, flatterndes DNS, fehlendes git,
#   leeres Repo — jeder dieser Faelle endet still mit Exit 0. Ein Hook, der
#   bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal
#   abgeschaltet und schuetzt danach gar nichts.
#
# WEITERE ZUSICHERUNGEN
#   - Ausgabe nur, wenn tatsaechlich Commits fehlen. Bei 0 schweigt er.
#   - Der Default-Branch wird per `ls-remote --symref` ermittelt, nicht als
#     "main" angenommen: im Portfolio heissen openlex-mcp, swiss-courts-mcp
#     und swisstopo-mcp ihren Default-Branch `master`. Genau diese Annahme
#     hat schon einmal einen Branch 15 Commits alt werden lassen.
#     `refs/remotes/origin/HEAD` ist als Quelle untauglich — in frisch
#     geklonten CI-/Web-Containern fehlt der Ref schlicht (hier: rc=1), und
#     nach einer Branch-Umbenennung zeigt er still auf den falschen Branch.
#   - Kurze Timeouts auf jeden Netzaufruf (Default 3s + 4s), damit der
#     Sessionstart nicht haengt.
#   - Rein lesend: fetch aktualisiert nur FETCH_HEAD, nie den Arbeitsbaum.
#
# Timeouts anpassbar via CLONE_FRESHNESS_LS_TIMEOUT / _FETCH_TIMEOUT.

# Absichtlich KEIN `set -e`: ein unerwarteter Nicht-Null-Status darf hier
# nichts abbrechen, sondern muss in den stillen Exit 0 unten laufen.
set -u

LS_TIMEOUT="${CLONE_FRESHNESS_LS_TIMEOUT:-3}"
FETCH_TIMEOUT="${CLONE_FRESHNESS_FETCH_TIMEOUT:-4}"

# --- Netzaufrufe hart deckeln ---------------------------------------------
_TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
  _TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  _TIMEOUT_BIN="gtimeout"
fi

# run_limited <sekunden> <befehl...>
run_limited() {
  local secs="$1"
  shift
  if [ -n "$_TIMEOUT_BIN" ]; then
    "$_TIMEOUT_BIN" -k 1 "$secs" "$@"
    return $?
  fi
  # Fallback ohne coreutils (z.B. macOS ohne brew): Waechter killt das Kind.
  # Die Ausgabe des Waechters MUSS nach /dev/null — sonst haelt er in einer
  # Kommandosubstitution die Pipe offen und das Timeout wird zur Wartezeit.
  "$@" &
  local pid=$!
  ( sleep "$secs"; kill -TERM "$pid" 2>/dev/null; sleep 1
    kill -KILL "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local watcher=$!
  wait "$pid" 2>/dev/null
  local rc=$?
  kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $rc
}

# --- Vorbedingungen: jede endet still -------------------------------------
command -v git >/dev/null 2>&1 || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ] || exit 0
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || exit 0

# Detached HEAD: gewollter Sonderzustand (bisect, Tag ausgecheckt). "Du liegt
# hinter main" waere dort erwartetes Rauschen — also schweigen.
git symbolic-ref --quiet HEAD >/dev/null 2>&1 || exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"
[ -n "$branch" ] || exit 0

[ -n "$(git config --get remote.origin.url 2>/dev/null)" ] || exit 0

# Nichts darf interaktiv nachfragen — ein Credential-Prompt haengt sonst den
# Sessionstart auf, bis der Nutzer Enter drueckt.
export GIT_TERMINAL_PROMPT=0
[ -n "${GIT_ASKPASS:-}" ] || export GIT_ASKPASS=true
[ -n "${SSH_ASKPASS:-}" ] || export SSH_ASKPASS=true
if [ -z "${GIT_SSH_COMMAND:-}" ] &&
   [ -z "$(git config --get core.sshCommand 2>/dev/null)" ]; then
  export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=3"
fi

# --- Default-Branch ermitteln (nicht annehmen) ----------------------------
default_branch="$(
  run_limited "$LS_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -n 1
)"
[ -n "$default_branch" ] || exit 0

# --- Abstand messen -------------------------------------------------------
run_limited "$FETCH_TIMEOUT" git fetch --quiet --no-tags origin \
  "$default_branch" >/dev/null 2>&1 || exit 0

behind="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"
case "$behind" in
  '' | *[!0-9]*) exit 0 ;;
esac
[ "$behind" -gt 0 ] || exit 0

if [ "$behind" -eq 1 ]; then noun="Commit"; else noun="Commits"; fi

cat <<MSG
Klon-Aktualitaet: '${branch}' liegt ${behind} ${noun} hinter origin/${default_branch}.
  Nachziehen:  git fetch origin ${default_branch} && git merge FETCH_HEAD
  Grund: Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff
  steht — die fehlenden Commits sind erfahrungsgemaess genau die, die das Gate
  einfuehren, an dem der Branch dann scheitert.
MSG

exit 0
