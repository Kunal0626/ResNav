#!/usr/bin/env bash
#
# run.sh -- single entry point for ResNav.
#
# Why a shell script and not just a Makefile: the credential handling below is
# the only safe way to hand a password to the mysql client, and it reads far
# better in shell than in make syntax. The Makefile delegates here, so there is
# exactly one implementation of every step.
#
# Usage: ./run.sh <target>
#   install  create the backend venv and install both dependency trees
#   check    verify MySQL access and that every SQL feature this project needs
#            is supported by the server you are pointed at
#   docs     grammar-check the Mermaid diagrams in docs/ (no database needed)
#   schema   apply db/schema, procedures, triggers and views
#   seed     load the sample data
#   reset    drop the database, then schema + seed
#   api      run the Flask development server (http://127.0.0.1:5001)
#   web      run the Vite development server (http://localhost:5173)
#   test     run the backend test suite and the SQL tests
#   concurrency  two-session race, isolation and deadlock experiments
#   lint     ruff over the backend, eslint over the frontend
#   build    production build of the frontend
#   demo     the end-to-end worked demo
#   shell    interactive mysql shell on the project database

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

VENV="$REPO_ROOT/backend/.venv"
PY="$VENV/bin/python"

# ---------------------------------------------------------------------------
# Configuration
#
# One .env configures the whole stack. We parse it literally rather than
# `source`-ing it: sourcing would execute whatever is in the file and would
# mangle passwords containing $, ` or \. Every key is then exported, because
# the Flask settings layer reads os.environ directly and does not parse .env
# itself -- without this export, the file would have no effect at all.
# ---------------------------------------------------------------------------

DRA_MYSQL_USER=""; DRA_MYSQL_PASSWORD=""; DRA_MYSQL_HOST=""
DRA_MYSQL_PORT=""; DRA_MYSQL_DB=""; MYSQL_BIN="${MYSQL_BIN:-}"

load_env() {
  if [[ ! -f .env ]]; then
    cat >&2 <<'MSG'
error: .env not found.

  cp .env.example .env && chmod 600 .env

then edit it. .env is git-ignored and configures the database, the API and
the frontend together.
MSG
    exit 1
  fi

  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "${line// }" ]] && continue
    [[ "${line#"${line%%[![:space:]]*}"}" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if   [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && ${#value} -ge 2 ]]; then value="${value:1:${#value}-2}"
    fi
    printf -v "$key" '%s' "$value"
    export "$key"
  done < .env

  : "${DRA_MYSQL_HOST:=127.0.0.1}"
  : "${DRA_MYSQL_PORT:=3306}"
  : "${DRA_MYSQL_DB:=resnav}"
  export DRA_MYSQL_HOST DRA_MYSQL_PORT DRA_MYSQL_DB
}

require_db_credentials() {
  local missing=()
  [[ -z "$DRA_MYSQL_USER" ]] && missing+=(DRA_MYSQL_USER)
  [[ -z "$DRA_MYSQL_PASSWORD" ]] && missing+=(DRA_MYSQL_PASSWORD)
  if (( ${#missing[@]} )); then
    echo "error: .env is missing: ${missing[*]}" >&2
    exit 1
  fi
}

find_mysql() {
  if [[ -n "$MYSQL_BIN" ]]; then
    [[ -x "$MYSQL_BIN" ]] || { echo "error: MYSQL_BIN=$MYSQL_BIN is not executable" >&2; exit 1; }
    return
  fi
  if command -v mysql >/dev/null 2>&1; then MYSQL_BIN="$(command -v mysql)"; return; fi
  local candidate
  for candidate in /usr/local/mysql/bin/mysql /usr/local/mysql-*/bin/mysql \
                   /opt/homebrew/opt/mysql/bin/mysql /usr/bin/mysql; do
    [[ -x "$candidate" ]] && { MYSQL_BIN="$candidate"; return; }
  done
  echo "error: mysql client not found. Set MYSQL_BIN in .env." >&2
  exit 1
}

DEFAULTS_FILE=""

# An EXIT trap's final exit status REPLACES the script's own. If the last
# command in here returned non-zero -- which a failed [[ ... ]] test does --
# every failure would be reported to make as a success. Hence `return 0`.
cleanup() {
  if [[ -n "$DEFAULTS_FILE" ]]; then
    rm -f "$DEFAULTS_FILE"
    rmdir "$(dirname "$DEFAULTS_FILE")" 2>/dev/null || true
  fi
  return 0
}
trap cleanup EXIT INT TERM

write_defaults_file() {
  local dir
  dir="$(mktemp -d "${TMPDIR:-/tmp}/resnav.XXXXXX")"
  DEFAULTS_FILE="$dir/client.cnf"
  ( umask 077; : > "$DEFAULTS_FILE" )   # 0600 before anything is written to it
  {
    printf '[client]\n'
    printf 'user=%s\n'     "$DRA_MYSQL_USER"
    printf 'password=%s\n' "$DRA_MYSQL_PASSWORD"
    printf 'host=%s\n'     "$DRA_MYSQL_HOST"
    printf 'port=%s\n'     "$DRA_MYSQL_PORT"
  } > "$DEFAULTS_FILE"
}

# --defaults-extra-file must be the client's FIRST argument.
mysql_raw() { "$MYSQL_BIN" "--defaults-extra-file=$DEFAULTS_FILE" "$@"; }
mysql_db()  { "$MYSQL_BIN" "--defaults-extra-file=$DEFAULTS_FILE" "$DRA_MYSQL_DB" "$@"; }

connect() { load_env; require_db_credentials; find_mysql; write_defaults_file; }

need_venv() {
  if [[ ! -x "$PY" ]]; then
    echo "error: backend virtualenv missing. Run:  ./run.sh install" >&2
    exit 1
  fi
}

# Locate npm, and put it on PATH for every subshell.
#
# nvm is a shell FUNCTION: it only puts node on PATH in a shell that has
# sourced nvm.sh. A script, a cron job, an IDE terminal, or a shell whose
# profile points nvm at the wrong location all end up without npm, and the
# failure looks like "npm: command not found" rather than anything useful.
# Resolving it ourselves means a clone builds without the user first having to
# repair their shell profile.
NPM_BIN=""
find_npm() {
  [[ -n "$NPM_BIN" ]] && return 0

  if command -v npm >/dev/null 2>&1; then
    NPM_BIN="$(command -v npm)"
    return 0
  fi

  local nvm_dir="${NVM_DIR:-$HOME/.nvm}" dir="" want=""
  if [[ -d "$nvm_dir/versions/node" ]]; then
    # Prefer whatever nvm calls "default"; otherwise the highest installed.
    [[ -r "$nvm_dir/alias/default" ]] && want="$(cat "$nvm_dir/alias/default")"
    if [[ -n "$want" ]]; then
      dir="$(find "$nvm_dir/versions/node" -maxdepth 1 -name "v${want#v}*" 2>/dev/null \
             | sort -V | tail -1)"
    fi
    [[ -z "$dir" ]] && dir="$(find "$nvm_dir/versions/node" -maxdepth 1 -name 'v*' 2>/dev/null \
                              | sort -V | tail -1)"
    if [[ -n "$dir" && -x "$dir/bin/npm" ]]; then
      # Prepend so npm can also find its own node.
      PATH="$dir/bin:$PATH"; export PATH
      NPM_BIN="$dir/bin/npm"
      return 0
    fi
  fi

  local candidate
  for candidate in /opt/homebrew/bin/npm /usr/local/bin/npm /usr/bin/npm; do
    if [[ -x "$candidate" ]]; then
      PATH="$(dirname "$candidate"):$PATH"; export PATH
      NPM_BIN="$candidate"
      return 0
    fi
  done

  cat >&2 <<'MSG'
error: npm not found.

Node 20+ is required to build the frontend. Checked: PATH, $NVM_DIR
(~/.nvm/versions/node), /opt/homebrew/bin, /usr/local/bin, /usr/bin.

If you installed Node with nvm, your shell has not loaded it. nvm is a shell
function, so it has to be sourced in your profile. Add to ~/.zshrc:

    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

then open a new terminal. Otherwise set the path explicitly:

    PATH=/path/to/node/bin:$PATH ./run.sh install
MSG
  exit 1
}

need_node_modules() {
  find_npm
  if [[ ! -d frontend/node_modules ]]; then
    echo "error: frontend dependencies missing. Run:  ./run.sh install" >&2
    exit 1
  fi
}

not_yet() {
  echo "error: '$1' is not built yet. It arrives in Phase $2." >&2
  echo "       See the Roadmap in README.md for what exists today." >&2
  exit 2
}

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

target_install() {
  echo "==> backend virtualenv"
  [[ -x "$PY" ]] || python3 -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r backend/requirements-dev.txt
  echo "    $("$PY" --version), dependencies installed"

  echo "==> frontend dependencies"
  find_npm
  ( cd frontend && "$NPM_BIN" install --silent )
  echo "    node $(node -v 2>/dev/null || echo '?') via $NPM_BIN, dependencies installed"

  echo
  echo "Next:  cp .env.example .env && chmod 600 .env   # then edit it"
  echo "       ./run.sh check"
}

target_check() {
  connect
  echo "==> client:  $MYSQL_BIN"
  echo "==> connect: $DRA_MYSQL_USER@$DRA_MYSQL_HOST:$DRA_MYSQL_PORT"
  echo

  if ! mysql_raw --connect-timeout=10 -e "SELECT 1" >/dev/null 2>"${TMPDIR:-/tmp}/resnav_conn.err"; then
    echo "FAIL: could not connect." >&2
    sed 's/^/       /' "${TMPDIR:-/tmp}/resnav_conn.err" >&2
    rm -f "${TMPDIR:-/tmp}/resnav_conn.err"
    exit 1
  fi
  rm -f "${TMPDIR:-/tmp}/resnav_conn.err"

  echo "--- server settings ------------------------------------------------"
  mysql_raw --table <<'SQL'
SELECT VARIABLE_NAME AS setting, VARIABLE_VALUE AS value
FROM performance_schema.global_variables
WHERE VARIABLE_NAME IN (
  'version','version_comment','default_storage_engine','sql_mode',
  'transaction_isolation','innodb_lock_wait_timeout','autocommit',
  'character_set_server','collation_server','lower_case_table_names',
  'log_bin','log_bin_trust_function_creators','max_connections',
  'innodb_deadlock_detect','innodb_buffer_pool_size'
)
ORDER BY VARIABLE_NAME;
SQL
  echo
  mysql_raw --table -e "SELECT CURRENT_USER() AS effective_user, @@hostname AS host_name;"
  echo
  echo "--- feature probe --------------------------------------------------"
  echo "    (creates probe_* objects in $DRA_MYSQL_DB and drops them afterwards)"
  echo

  # --force so the client keeps going after a refused statement. Without it a
  # single missing privilege hides every other answer, and the whole point of
  # the probe is to learn as much as possible in one run. Nothing is masked:
  # each refusal is printed, every passing feature still records its row, and
  # the sentinel row at the end is what says the script reached the bottom.
  local probe_status=0
  mysql_db --force < tools/capabilities.sql || probe_status=$?

  mysql_db --table -e \
    "SELECT seq, feature, verdict, detail FROM probe_result ORDER BY seq;"

  local failures completed
  failures=$(mysql_db -N -B -e \
    "SELECT COUNT(*) FROM probe_result WHERE verdict <> 'PASS';")
  completed=$(mysql_db -N -B -e \
    "SELECT COUNT(*) FROM probe_result WHERE feature = 'probe_completed';")

  mysql_db -e "DROP TABLE IF EXISTS probe_result;"

  echo
  if [[ "$completed" != "1" ]]; then
    echo "RESULT: INCOMPLETE -- the probe stopped early (exit $probe_status)."
    echo "        The error above names the statement the server refused."
    return 1
  fi
  if [[ "$failures" != "0" ]]; then
    echo "RESULT: $failures probe(s) FAILED. Do not build on this server until they pass."
    return 1
  fi
  echo "RESULT: all probes PASS. This server supports everything the project needs."
}

# Grammar-checks the ER diagrams. Needs no database, so it works before .env
# exists. This is a grammar check, NOT a render: it catches what makes GitHub
# show an error box, not whether the picture reads well.
target_docs() {
  python3 -I tools/check_mermaid.py docs/*.md
}

target_api() {
  load_env; need_venv
  echo "==> Flask on http://127.0.0.1:5001  (APP_ENV=${APP_ENV:-development})"
  cd backend && exec "$PY" manage.py run
}

target_web() {
  need_node_modules
  echo "==> Vite on http://localhost:5173  (proxies /api to 127.0.0.1:5001)"
  cd frontend && exec "$NPM_BIN" run dev
}

target_test() {
  load_env; need_venv
  echo "==> backend test suite (against MySQL)"
  # No database rebuild workaround here any more. The suite reloads
  # db/seed/*.sql before every test, so no test can see another's writes --
  # the defect recorded in docs/AUDIT.md is fixed rather than worked around,
  # and tests/test_config.py asserts it.
  ( cd backend && "$PY" -m pytest -q ) || return 1

  echo
  echo "==> SQL test suite"
  # The runner never touches a password: connect() has already written the
  # 0600 defaults file, and its path is all that is handed over. One place in
  # the repo deals with credentials.
  connect
  local status=0
  RESNAV_MYSQL_BIN="$MYSQL_BIN" \
  RESNAV_MYSQL_DEFAULTS_FILE="$DEFAULTS_FILE" \
  RESNAV_MYSQL_DB="$DRA_MYSQL_DB" \
    python3 -I db/tests/runner.py "$@" || status=$?

  # Both suites leave the database holding their own last writes. Reloading
  # the seed means `make test` is also the way back to a known-good state.
  echo
  echo "==> restoring the seed"
  local f
  for f in db/seed/*.sql; do mysql_db < "$f"; done
  return $status
}

target_lint() {
  need_venv; need_node_modules
  echo "==> ruff"
  # db/ and tools/ hold real Python too -- the seed generator, the SQL test
  # runner and the concurrency experiments -- so they are linted as well.
  ( cd backend && "$PY" -m ruff check . )
  "$PY" -m ruff check db/ tools/
  echo "==> eslint"
  ( cd frontend && "$NPM_BIN" run lint )
}

target_build() {
  need_node_modules
  ( cd frontend && "$NPM_BIN" run build )
}

# The two-session experiments. Separate from `test` because they take
# tens of seconds, deliberately provoke deadlocks and lock-wait timeouts,
# and two of them are supposed to demonstrate failure rather than success.
target_concurrency() {
  load_env; need_venv
  connect   # exports nothing, but fails early if the database is unreachable
  "$PY" -I db/tests/concurrency/run_all.py "$@"
}

target_shell() {
  connect
  # Deliberately NOT `exec`. mysql_db is a shell function, which exec cannot
  # replace the process with -- and even with the binary spelled out, exec
  # would discard the EXIT trap and leak the temporary credentials file.
  # Arguments are forwarded, so `./run.sh shell -e "SELECT 1"` works and
  # `./run.sh shell < file.sql` still does too.
  mysql_db "$@"
}

# Applies db/ in dependency order. Every file drops before it creates, so
# running this twice is not an error and does not need a dropped database.
target_schema() {
  connect
  local f
  for f in db/schema/*.sql db/procedures/*.sql db/triggers/*.sql db/views/*.sql; do
    [[ -e "$f" ]] || continue
    printf '  applying %s\n' "$f"
    if ! mysql_db < "$f"; then
      echo "error: $f failed. Nothing after it was applied." >&2
      return 1
    fi
  done
  echo
  mysql_db --table -e "
    SELECT 'tables'    AS object, COUNT(*) AS n FROM information_schema.TABLES    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
    UNION ALL SELECT 'views',     COUNT(*) FROM information_schema.VIEWS          WHERE TABLE_SCHEMA = DATABASE()
    UNION ALL SELECT 'triggers',  COUNT(*) FROM information_schema.TRIGGERS       WHERE TRIGGER_SCHEMA = DATABASE()
    UNION ALL SELECT 'routines',  COUNT(*) FROM information_schema.ROUTINES       WHERE ROUTINE_SCHEMA = DATABASE()
    UNION ALL SELECT 'foreign keys', COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND CONSTRAINT_TYPE='FOREIGN KEY'
    UNION ALL SELECT 'check constraints', COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND CONSTRAINT_TYPE='CHECK';"
}
target_seed() {
  connect
  local f
  for f in db/seed/*.sql; do
    [[ -e "$f" ]] || { echo "error: no seed files in db/seed/" >&2; return 1; }
    printf '  loading %s\n' "$f"
    mysql_db < "$f" || return 1
  done
  mysql_db --table -e "
    SELECT 'providers' AS entity, COUNT(*) AS n FROM Providers
    UNION ALL SELECT 'resources',  COUNT(*) FROM Resources
    UNION ALL SELECT 'zones',      COUNT(*) FROM Zones
    UNION ALL SELECT 'stock rows', COUNT(*) FROM StockLevels
    UNION ALL SELECT 'requests',   COUNT(*) FROM Requests;"
}
# Rebuild from nothing: schema, then data. The schema files drop before they
# create, so this needs no DROP DATABASE and no extra privilege.
target_reset() {
  target_schema && echo && target_seed
}
target_demo()   { not_yet demo 8; }

usage() {
  # Print the Usage block from this file's own header, so the help text and
  # the real target list cannot drift apart.
  sed -n '/^# Usage: /,/^$/p' "$0" | sed 's/^#\{1,\} \{0,1\}//;s/^#$//'
  exit 1
}

main() {
  local target="${1:-}"
  # Drop the target name so the rest can be forwarded. `shell` in particular
  # is useless without it: `./run.sh shell -e "SELECT 1"` previously ignored
  # the -e entirely and sat waiting on stdin.
  [[ $# -gt 0 ]] && shift
  case "$target" in
    install) target_install ;;
    check)   target_check ;;
    docs)    target_docs ;;
    schema)  target_schema ;;
    seed)    target_seed ;;
    reset)   target_reset ;;
    api)     target_api ;;
    web)     target_web ;;
    test)    target_test "$@" ;;
    lint)    target_lint ;;
    build)   target_build ;;
    demo)    target_demo ;;
    concurrency) target_concurrency "$@" ;;
    shell)   target_shell "$@" ;;
    ""|-h|--help|help) usage ;;
    *) echo "error: unknown target '${target}'" >&2; echo >&2; usage ;;
  esac
}

main "$@"
