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
  echo "    (uses a scratch database, dra_probe_tmp, and drops it afterwards)"
  echo

  # Run tolerantly: if a statement aborts the script we still want to print
  # what was recorded, because the missing sentinel row plus the client's own
  # error message is how we find out what the server refused.
  local probe_status=0
  mysql_raw < tools/capabilities.sql || probe_status=$?

  mysql_raw --table -e \
    "SELECT seq, feature, verdict, detail FROM dra_probe_tmp.probe_result ORDER BY seq;"

  local failures completed
  failures=$(mysql_raw -N -B -e \
    "SELECT COUNT(*) FROM dra_probe_tmp.probe_result WHERE verdict <> 'PASS';")
  completed=$(mysql_raw -N -B -e \
    "SELECT COUNT(*) FROM dra_probe_tmp.probe_result WHERE feature = 'probe_completed';")

  mysql_raw -e "DROP DATABASE IF EXISTS dra_probe_tmp;"

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
  # The suite still runs against SQLite; Phase 4 ports it to MySQL and this
  # target grows the SQL tests in Phase 3.
  #
  # Rebuilding the database below is a WORKAROUND for a real defect, not
  # housekeeping.
  #
  # tests/conftest.py builds an isolated temporary database per test, but
  # db/connection.py:connect() resolves its path from the lru_cached GLOBAL
  # get_settings(), not from the Settings the test injected into create_app.
  # So every request opens backend/instance/resource_navigator.db instead --
  # the developer's real database -- and the tests mutate it as they run.
  #
  # The suite is therefore NOT idempotent. Measured: against one database it
  # passes twice, then fails from the third run onward, because allocation
  # tests drain stock (2505 -> 2460 -> 2430 units) until the partial-
  # fulfilment test can no longer get a partial result. Deleting and
  # re-seeding makes the target reproducible; it does not fix the bug.
  #
  # See docs/AUDIT.md "Broken test isolation". Fixed properly in Phase 4.
  echo "==> rebuilding backend/instance (see docs/AUDIT.md: broken test isolation)"
  rm -rf backend/instance
  ( cd backend && "$PY" manage.py seed >/dev/null )
  echo "==> backend test suite"
  ( cd backend && "$PY" -m pytest -q )
}

target_lint() {
  need_venv; need_node_modules
  echo "==> ruff"
  ( cd backend && "$PY" -m ruff check . )
  echo "==> eslint"
  ( cd frontend && "$NPM_BIN" run lint )
}

target_build() {
  need_node_modules
  ( cd frontend && "$NPM_BIN" run build )
}

target_shell() { connect; exec mysql_db; }

target_schema() { not_yet schema 3; }
target_seed()   { not_yet seed 5; }
target_reset()  { not_yet reset 5; }
target_demo()   { not_yet demo 8; }

usage() {
  # Print the Usage block from this file's own header, so the help text and
  # the real target list cannot drift apart.
  sed -n '/^# Usage: /,/^$/p' "$0" | sed 's/^#\{1,\} \{0,1\}//;s/^#$//'
  exit 1
}

main() {
  case "${1:-}" in
    install) target_install ;;
    check)   target_check ;;
    docs)    target_docs ;;
    schema)  target_schema ;;
    seed)    target_seed ;;
    reset)   target_reset ;;
    api)     target_api ;;
    web)     target_web ;;
    test)    target_test ;;
    lint)    target_lint ;;
    build)   target_build ;;
    demo)    target_demo ;;
    shell)   target_shell ;;
    ""|-h|--help|help) usage ;;
    *) echo "error: unknown target '${1}'" >&2; echo >&2; usage ;;
  esac
}

main "$@"
