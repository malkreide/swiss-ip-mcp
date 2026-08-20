#!/usr/bin/env bash
#
# Tests fuer check-clone-freshness.sh.
#
# Ohne Argument: die Zusicherungen pruefen.
# Mit --gegenprobe: jede Zusicherung einzeln aus dem Skript entfernen und
# zeigen, dass genau die zugehoerigen Faelle fallen. Ein Test, der gruen
# bleibt, wenn man die Implementierung entfernt, prueft nichts (CLAUDE.md).
#
# Baut echte Repos mit lokalem origin — keine handgeschriebenen Fixtures, die
# nur die Annahme des Autors zurueckspielen.

set -u

HOOK_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-clone-freshness.sh"
HOOK="${HOOK_OVERRIDE:-$HOOK_DEFAULT}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0
FAILED_CASES=""

# --- Gegenprobe-Treiber ----------------------------------------------------
# Entfernt je EINE Zusicherung aus dem Skript und prueft, dass genau die
# zugehoerigen Faelle fallen. Die Mutation wird per assert verankert: eine
# Mutation, die still nicht greift, wuerde eine Gegenprobe vortaeuschen.
if [ "${1:-}" = "--gegenprobe" ]; then
  GP="$WORK/gp"; mkdir -p "$GP"
  gp_fail=0

  mutate() { # mutate <name> <alt> <neu> <erwartete-fehler...>
    local name="$1" old="$2" new="$3"; shift 3
    local mutant="$GP/$name.sh" got exp="$*"
    if ! python3 -c '
import sys
src = open(sys.argv[1]).read()
old, new = sys.argv[3], sys.argv[4]
assert old in src, "Mutationsanker nicht gefunden"
open(sys.argv[2], "w").write(src.replace(old, new, 1))
' "$HOOK" "$mutant" "$old" "$new"; then
      printf "  FAIL %-28s Mutation liess sich nicht anwenden\n" "$name"
      gp_fail=$((gp_fail + 1)); return
    fi
    HOOK_OVERRIDE="$mutant" GEGENPROBE_EXPORT="$GP/$name.out" \
      bash "${BASH_SOURCE[0]}" >/dev/null 2>&1
    got="$(cat "$GP/$name.out" 2>/dev/null)"
    got="$(echo $got)"; exp="$(echo $exp)"
    if [ "$got" = "$exp" ]; then
      printf "  ok   %-28s faellt bei: %s\n" "$name" "$got"
    else
      printf "  FAIL %-28s erwartet [%s], gefallen [%s]\n" "$name" "$exp" "$got"
      gp_fail=$((gp_fail + 1))
    fi
  }

  echo "== Gegenprobe: Zusicherung entfernen, Test muss fallen =="

  mutate default-branch-hartkodiert \
    '[ -n "$default_branch" ] || exit 0' \
    'default_branch=main
[ -n "$default_branch" ] || exit 0' \
    "master-Repo -> origin/master"

  mutate schweigen-bei-0 \
    '[ "$behind" -gt 0 ] || exit 0' \
    ':' \
    "aktueller Klon schweigt eigene Commits, 0 hinter -> still"

  mutate detached-head-guard \
    'git symbolic-ref --quiet HEAD >/dev/null 2>&1 || exit 0
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"
[ -n "$branch" ] || exit 0' \
    'branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"' \
    "detached HEAD"

  mutate kein-timeout \
    '# --- Vorbedingungen' \
    'run_limited() { shift; "$@"; }
# --- Vorbedingungen' \
    "haengender Remote bricht ab"

  mutate fetch-fehler-blockiert \
    '"$default_branch" >/dev/null 2>&1 || exit 0' \
    '"$default_branch" >/dev/null 2>&1 || exit 1' \
    "fetch scheitert (origin defekt)"

  # Anmerkung: '|| true' allein ist hier NICHT widerlegbar — git kuerzt
  # FETCH_HEAD beim Start jedes fetch, ein veralteter Wert bleibt also nicht
  # liegen (geprueft mit git 2.43). Widerlegbar wird es erst zusammen mit dem
  # entfernten Zahlenwaechter: dann rechnet der Test mit einem leeren String.
  mutate zahlenwaechter-weg \
    '"$default_branch" >/dev/null 2>&1 || exit 0

behind="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"
case "$behind" in
  '"'"''"'"' | *[!0-9]*) exit 0 ;;
esac' \
    '"$default_branch" >/dev/null 2>&1 || true

behind="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"' \
    "fetch scheitert (origin defekt)"

  printf "\nGegenprobe: %d Mutation(en) ohne erwarteten Ausfall\n" "$gp_fail"
  [ "$gp_fail" -eq 0 ]
  exit $?
fi


# Umgebung neutralisieren: nichts aus der aufrufenden Session darf durchschlagen.
unset CLAUDE_PROJECT_DIR GIT_DIR GIT_WORK_TREE 2>/dev/null
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t
export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

check() { # check <name> <erwartung: has|silent> <muster> <ausgabe> <rc> [<dauer>] [<maxdauer>]
  local name="$1" mode="$2" pattern="$3" out="$4" rc="$5" dur="${6:-}" max="${7:-}"
  local ok=1 why=""
  if [ "$rc" -ne 0 ]; then ok=0; why="Exit $rc statt 0 (haette die Session blockiert)"; fi
  # Ein Hook, der beim Sessionstart auf stderr schreibt, ist Laerm — und bei
  # Nicht-Null-Exit zeigt Claude Code diesen Text dem Nutzer.
  [ -z "${ERR:-}" ] || { ok=0; why="${why:+$why; }schrieb auf stderr: '"'"'${ERR}'"'"'"; }
  case "$mode" in
    has)
      case "$out" in *"$pattern"*) ;; *) ok=0; why="${why:+$why; }Ausgabe enthaelt '$pattern' nicht: '${out}'";; esac ;;
    silent)
      [ -z "$out" ] || { ok=0; why="${why:+$why; }haette schweigen muessen, sagte: '${out}'"; } ;;
  esac
  if [ -n "$max" ] && [ "${dur:-0}" -gt "$max" ]; then
    ok=0; why="${why:+$why; }brauchte ${dur}s, erlaubt sind ${max}s"
  fi
  if [ "$ok" -eq 1 ]; then
    pass=$((pass + 1)); printf '  ok   %s\n' "$name"
  else
    fail=$((fail + 1)); FAILED_CASES="${FAILED_CASES}${name} "
    printf '  FAIL %s -- %s\n' "$name" "$why"
  fi
}

run_hook() { # run_hook <repo> -> setzt OUT, RC, DUR
  local repo="$1" start end
  start=$(date +%s)
  OUT="$(CLAUDE_PROJECT_DIR="$repo" bash "$HOOK" 2>"$WORK/stderr")"
  RC=$?
  ERR="$(cat "$WORK/stderr" 2>/dev/null)"
  end=$(date +%s)
  DUR=$((end - start))
}

# Baut origin (mit gewuenschtem Default-Branch) + Klon.
# make_repo <name> <default-branch> <commits-in-origin-nach-klon>
make_repo() {
  local name="$1" defbranch="$2" extra="$3"
  local origin="$WORK/$name.git" clone="$WORK/$name"
  git init --quiet --bare --initial-branch="$defbranch" "$origin"
  git init --quiet --initial-branch="$defbranch" "$WORK/seed-$name"
  (
    cd "$WORK/seed-$name" || exit 1
    echo seed > f.txt; git add f.txt; git commit --quiet -m seed
    git push --quiet "$origin" "$defbranch"
  ) >/dev/null 2>&1
  git clone --quiet "$origin" "$clone" >/dev/null 2>&1
  local i=1
  while [ "$i" -le "$extra" ]; do
    (
      cd "$WORK/seed-$name" || exit 1
      echo "c$i" >> f.txt; git add f.txt; git commit --quiet -m "c$i"
      git push --quiet "$origin" "$defbranch"
    ) >/dev/null 2>&1
    i=$((i + 1))
  done
  printf '%s' "$clone"
}

echo "== Zusicherung 1: meldet, wenn Commits fehlen =="
R="$(make_repo behind main 3)"
run_hook "$R"; check "3 Commits hinter origin/main" has "3 Commits hinter origin/main" "$OUT" "$RC"

echo "== Zusicherung 2: bei 0 schweigt er =="
R="$(make_repo aktuell main 0)"
run_hook "$R"; check "aktueller Klon schweigt" silent "" "$OUT" "$RC"

echo "== Zusicherung 3: Default-Branch ermittelt, nicht 'main' angenommen =="
R="$(make_repo masterrepo master 2)"
run_hook "$R"; check "master-Repo -> origin/master" has "2 Commits hinter origin/master" "$OUT" "$RC"

echo "== Zusicherung 4: nur 'hinter' zaehlt, nicht 'vor' =="
R="$(make_repo vorne main 0)"
( cd "$R" && echo lokal >> f.txt && git add f.txt && git commit --quiet -m lokal ) >/dev/null 2>&1
run_hook "$R"; check "eigene Commits, 0 hinter -> still" silent "" "$OUT" "$RC"

echo "== Zusicherung 5: blockiert nie =="
R="$(make_repo detached main 3)"
( cd "$R" && git checkout --quiet --detach HEAD ) >/dev/null 2>&1
run_hook "$R"; check "detached HEAD" silent "" "$OUT" "$RC"

R="$(make_repo kein_origin main 0)"
( cd "$R" && git remote remove origin ) >/dev/null 2>&1
run_hook "$R"; check "kein origin-Remote" silent "" "$OUT" "$RC"

mkdir -p "$WORK/kein_repo"
run_hook "$WORK/kein_repo"; check "kein git-Repo" silent "" "$OUT" "$RC"

run_hook "$WORK/gibt-es-nicht"; check "Verzeichnis fehlt" silent "" "$OUT" "$RC"

git init --quiet "$WORK/leer" && ( cd "$WORK/leer" && git remote add origin "$WORK/behind.git" ) >/dev/null 2>&1
run_hook "$WORK/leer"; check "Repo ohne Commit" silent "" "$OUT" "$RC"

# ls-remote gelingt (Refs lesbar), fetch scheitert (Objekte weg). Der
# vorherige erfolgreiche Fetch legt ein veraltetes FETCH_HEAD ab: wer den
# fetch-Exitcode ignoriert, meldet daraus eine Zahl, die er nicht gemessen hat.
R="$(make_repo defekt main 2)"
( cd "$R" && git fetch --quiet --no-tags origin main ) >/dev/null 2>&1
(
  cd "$WORK/seed-defekt" || exit 1
  echo c3 >> f.txt; git add f.txt; git commit --quiet -m c3
  git push --quiet "$WORK/defekt.git" main
) >/dev/null 2>&1
rm -rf "$WORK/defekt.git/objects" && mkdir -p "$WORK/defekt.git/objects"
run_hook "$R"; check "fetch scheitert (origin defekt)" silent "" "$OUT" "$RC"

R="$(make_repo dns main 0)"
( cd "$R" && git remote set-url origin \
    "https://kein-solcher-host.invalid/x.git" ) >/dev/null 2>&1
run_hook "$R"; check "Remote nicht aufloesbar (DNS)" silent "" "$OUT" "$RC"

echo "== Zusicherung 6: kurzes Timeout, Sessionstart haengt nicht =="
# 'ext::sleep 30' ist ein Remote, der garantiert haengt — deterministisch,
# im Gegensatz zu einem Host, der zufaellig schnell ablehnt.
R="$(make_repo haenger main 0)"
(
  cd "$R" || exit 1
  git remote set-url origin "ext::sleep 30"
  git config protocol.ext.allow always
) >/dev/null 2>&1
run_hook "$R"; check "haengender Remote bricht ab" silent "" "$OUT" "$RC" "$DUR" 12

printf '\n%s: %d ok, %d fehlgeschlagen\n' "$(basename "$HOOK")" "$pass" "$fail"
[ -n "${GEGENPROBE_EXPORT:-}" ] && printf '%s' "$FAILED_CASES" > "$GEGENPROBE_EXPORT"
[ "$fail" -eq 0 ]
