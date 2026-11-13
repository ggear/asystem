#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

#   restore.sh [--mode=replace|merge|drill] [--from=<timestamp>] [--file=<path>] [--runs=<dir>]
#              [--record=<stage>] [--keep-scratch] [--force] [--no-backup]
#
#   bare      read only, resolves the chain and prints the plan, changes nothing
#   --force   applies the plan, the only destructive form
#
#   mode      replace restores wholesale, drill proves the backup restores without touching live,
#             merge puts back history live lost, offered only to a module defining restore_merged
#   from      the run to restore, a backup timestamp, defaulting to the newest run not regressed
#   file      an artefact path outright, for one lifted off the share or elsewhere
#   runs      a directory of runs searched alone, for a chain pinned outside the stages
#   record    the stage under whose .meta a drill writes its verdict, primary or secondary
#   keep-scratch  leave the scratch directory behind for inspection
#   no-backup skip the safety backup taken of the current data before applying
#
# The run is `supervisor backup restore|drill|merge`, this script holds only the module's own hooks.
# Only install.sh runs it unprompted, as a drill after a release, which touches nothing live. Applying is only ever by hand.

set -uo pipefail

RESTORE_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${RESTORE_INTERNAL_ENV}" ] && . "${RESTORE_INTERNAL_ENV}"

RESTORE_MODULE_NAME="postgres"
RESTORE_SOURCE_PATH="${RESTORE_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/postgres/latest}}"
RESTORE_INTERNAL_SOURCE_DIR="$(readlink -f "${RESTORE_SOURCE_PATH}")"
RESTORE_FULL_SUFFIX="_full"
RESTORE_DELTA_SUFFIX="_delta"
RESTORE_SERVICE_STATE="stopped"
RESTORE_RUN_TIMESTAMP="${RESTORE_RUN_TIMESTAMP:-}"
RESTORE_CHAIN_FILES=()
[ -n "${RESTORE_CHAIN_LIST:-}" ] && mapfile -t RESTORE_CHAIN_FILES <<<"${RESTORE_CHAIN_LIST}"
RESTORE_SOURCE_FILE="${RESTORE_CHAIN_FILES[*]: -1}"
RESTORE_CARRY=()

restore_module() { "${RESTORE_SUPERVISOR:-/asystem/bin/supervisor}" backup "$@"; }

restore_report() { restore_module report "$*"; }

restore_changed() { restore_report "$@"; }

restore_fault() { echo "❌ $*" >&2; }

restore_stamped() {
  local label="${1}"
  shift
  restore_report "${label} $(date +%T) $*" >&2
}

restore_scratch_dir() { printf '%s\n' "$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")/restore/${RESTORE_RUN_TIMESTAMP}"; }

restore_service_state() { printf '%s\n' "${RESTORE_SERVICE_STATE}"; }

restore_live_address() { printf '%s\n' "${RESTORE_LIVE_ADDRESS:-}"; }

restore_files() {
  local arguments=() entry
  for entry in "${RESTORE_CARRY[@]}"; do arguments+=("--carry=${entry}"); done
  restore_module restore-files "${RESTORE_MODULE_NAME}" --source "${RESTORE_INTERNAL_SOURCE_DIR}" --run "${RESTORE_RUN_TIMESTAMP}" \
    --target "${2:-${RESTORE_SOURCE_PATH}}" --file "${RESTORE_SOURCE_FILE}" --paths "${1:-}" "${arguments[@]}"
}

# The engine owns the run, this snippet owns the restore. `supervisor backup restore` resolves the chain, checks
# its integrity, takes a safety backup, stops or starts the service, counts faults and sets the exit code, calling
# this snippet's hooks, each in its own bash. Define restore_applied below, reading "${RESTORE_SOURCE_FILE}" and
# writing it back into the service, and optionally restore_planned to describe that in the dry run. Declare
# RESTORE_SERVICE_STATE as "stopped" when the restore replaces files the service holds open, or "running" when
# it is applied through the service itself. A snippet with a scratch copy also defines restore_staged (print the
# scratch address), restore_sealed, restore_teardown and restore_checked, one with live history to merge
# restore_merged, and one with units still being written restore_settled, a stdin to stdout filter dropping the
# open ones. No hook may rely on a variable another set. Never assign another wrapper variable, prefix this
# snippet's own state with the module name, and expand a value read from .env as "${VAR:?}", so a missing key
# fails by name rather than corrupting the restore.
#
# RESTORE_MODULE_NAME     this module's name
# RESTORE_SOURCE_PATH     this module's data path, the restore target
# RESTORE_SOURCE_FILE     the artefact being restored from
# RESTORE_CHAIN_FILES     every artefact of the chain, oldest first
# RESTORE_RUN_TIMESTAMP   the timestamp of the run the artefact belongs to
# RESTORE_FULL_SUFFIX     the file suffix marking a full backup
# RESTORE_DELTA_SUFFIX    the file suffix marking a delta backup
# RESTORE_SERVICE_STATE   the state the service must be in, stopped or running
RESTORE_SERVICE_STATE="running"

restore_planned() {
  restore_report "would drop each database the dump names, then load the cluster dump into a running [${RESTORE_MODULE_NAME}]"
  restore_report "with the existing [postgres] role line removed and the TimescaleDB catalog loaded between [timescaledb_pre_restore] and [timescaledb_post_restore]"
  restore_report "set [POSTGRES_RESTORE_TIMESCALEDB_VERSION] to the extension version the dump was taken at when it differs from the image's, which is the case for a dump taken before the extension update"
  restore_report "the wrangle database is not in the dump and is rebuilt by wrangle, and the Home Assistant recorder's"
  restore_report "states, events and short term statistics come back empty, only their schema is dumped"
}

POSTGRES_RESTORE_SCRATCH="${RESTORE_MODULE_NAME}_restore"
POSTGRES_RESTORE_PORT="${POSTGRES_RESTORE_PORT:-15433}"
POSTGRES_RESTORE_TIMESCALEDB_VERSION="${POSTGRES_RESTORE_TIMESCALEDB_VERSION:-}"

postgres_restore_stream() {
  gzip -dc "${RESTORE_SOURCE_FILE}" | awk -v version="${POSTGRES_RESTORE_TIMESCALEDB_VERSION}" '
    /^CREATE ROLE postgres;$/ { next }
    /^CREATE EXTENSION IF NOT EXISTS timescaledb / {
      if (version != "") sub(/WITH SCHEMA public/, "WITH SCHEMA public VERSION \047" version "\047")
      print
      print "SELECT public.timescaledb_pre_restore();"
      pending = 1
      next
    }
    /^\\connect / {
      if (pending) print "SELECT public.timescaledb_post_restore();"
      pending = 0
    }
    { print }
    END { if (pending) print "SELECT public.timescaledb_post_restore();" }'
}

postgres_restore_databases() {
  gzip -dc "${RESTORE_SOURCE_FILE}" | sed -n 's/^CREATE DATABASE \([^ ]*\) .*/\1/p'
}

postgres_restore_loaded() {
  local container="${1}" user="${2}" database
  for database in postgres template1; do
    docker exec --user root --env PGOPTIONS="-c client_min_messages=warning" "${container}" psql -U "${user}" -d "${database}" -v ON_ERROR_STOP=1 -qc "DROP EXTENSION IF EXISTS timescaledb CASCADE" >/dev/null || return 1
  done
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root --env PGOPTIONS="-c client_min_messages=warning" "${container}" psql -U "${user}" -d postgres -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS \"${database}\" WITH (FORCE)" >/dev/null || return 1
  done < <(postgres_restore_databases)
  postgres_restore_stream | docker exec --interactive --user root "${container}" psql -U "${user}" -d postgres -v ON_ERROR_STOP=1 -q >/dev/null
}

backup_fingerprinted() {
  local container="${1:-${RESTORE_MODULE_NAME}}" user database
  user="postgres"
  [ "${container}" = "${RESTORE_MODULE_NAME}" ] && user="${POSTGRES_USER:?}"
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root "${container}" psql -U "${user}" -d "${database}" -Atc "
      SELECT '${database}.' || schemaname || '.' || tablename || ' ' ||
        (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', schemaname, tablename), false, true, '')))[1]::text
      FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1" || return 1
  done < <(docker exec --user root "${container}" psql -U "${user}" -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname") | sort
}

restore_staged() {
  local image scratch waited=0
  scratch="$(restore_scratch_dir)"
  image="$(docker inspect "${RESTORE_MODULE_NAME}" --format '{{.Config.Image}}')" || return 1
  rm -rf "${scratch}"
  mkdir -p "${scratch}" || return 1
  docker rm -f "${POSTGRES_RESTORE_SCRATCH}" >/dev/null 2>&1
  docker run --detach --name "${POSTGRES_RESTORE_SCRATCH}" --publish "127.0.0.1:${POSTGRES_RESTORE_PORT}:5432" \
    --env POSTGRES_PASSWORD=scratch --env POSTGRES_USER=postgres --volume "${scratch}:/var/lib/postgresql" \
    "${image}" >/dev/null || return 1
  until docker exec "${POSTGRES_RESTORE_SCRATCH}" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do
    waited=$((waited + 1))
    [ "${waited}" -le 180 ] || { restore_fault "scratch [${POSTGRES_RESTORE_SCRATCH}] did not accept connections within [180] seconds"; return 1; }
    sleep 1
  done
  postgres_restore_loaded "${POSTGRES_RESTORE_SCRATCH}" postgres || {
    restore_fault "could not load [${RESTORE_SOURCE_FILE}] into scratch [${POSTGRES_RESTORE_SCRATCH}]"
    return 1
  }
  printf '%s\n' "${POSTGRES_RESTORE_SCRATCH}"
}

restore_sealed() {
  local database failed=0
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root --env PGOPTIONS="-c default_transaction_read_only=off" "${POSTGRES_RESTORE_SCRATCH}" \
      psql -U postgres -d postgres -v ON_ERROR_STOP=1 -qc "ALTER DATABASE \"${database}\" SET default_transaction_read_only = on" >/dev/null || failed=1
  done < <(docker exec --user root "${POSTGRES_RESTORE_SCRATCH}" psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn")
  return "${failed}"
}

restore_teardown() {
  docker rm -f "${POSTGRES_RESTORE_SCRATCH}" >/dev/null 2>&1
  rm -rf "$(restore_scratch_dir)"
}

restore_applied() {
  postgres_restore_loaded "${RESTORE_MODULE_NAME}" "${POSTGRES_USER:?}" || {
    restore_fault "could not load the cluster dump into [${RESTORE_MODULE_NAME}]"
    return 1
  }
  restore_changed "loaded the cluster dump into [${RESTORE_MODULE_NAME}]"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

RESTORE_INTERNAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"

restore_supervised() {
  local container image seconds="${RESTORE_TIMEOUT_SECONDS:-86400}"
  if [ -x /asystem/bin/supervisor ]; then
    exec /asystem/bin/supervisor backup "$@"
  fi
  container="$(timeout 30 docker ps --filter name=^/supervisor$ --filter status=running --format '{{.Names}}')"
  if [ -n "${container}" ]; then
    exec timeout "${seconds}" docker exec supervisor /asystem/bin/supervisor backup "$@"
  fi
  image="$(timeout 30 docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^supervisor:' | sort -V | tail -n 1)"
  [ -n "${image}" ] || { echo "No supervisor container is running and no supervisor image is installed, cannot run the restore" >&2; exit 1; }
  exec timeout "${seconds}" docker run --rm --init --entrypoint /asystem/bin/supervisor \
    --volume /home/asystem:/home/asystem --volume /share:/share --volume /var/lib/asystem/install:/var/lib/asystem/install:ro --volume /var/run/docker.sock:/var/run/docker.sock \
    "${image}" backup "$@"
}

RESTORE_INTERNAL_MODE="replace"
RESTORE_INTERNAL_ARGUMENTS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
  --force) RESTORE_INTERNAL_ARGUMENTS+=(--force) ;;
  --no-backup) RESTORE_INTERNAL_ARGUMENTS+=(--no-backup) ;;
  --keep-scratch) RESTORE_INTERNAL_ARGUMENTS+=(--keep-scratch) ;;
  --from=*) RESTORE_INTERNAL_ARGUMENTS+=(--from "${1#--from=}") ;;
  --from)
    shift
    RESTORE_INTERNAL_ARGUMENTS+=(--from "${1:-}")
    ;;
  --file=*) RESTORE_INTERNAL_ARGUMENTS+=(--file "${1#--file=}") ;;
  --file)
    shift
    RESTORE_INTERNAL_ARGUMENTS+=(--file "${1:-}")
    ;;
  --runs=*) RESTORE_INTERNAL_ARGUMENTS+=(--runs "${1#--runs=}") ;;
  --record=*) RESTORE_INTERNAL_ARGUMENTS+=(--record "${1#--record=}") ;;
  --mode=*) RESTORE_INTERNAL_MODE="${1#--mode=}" ;;
  *)
    echo "Usage: ${0} [--mode=replace|merge|drill] [--from=<timestamp>] [--file=<path>] [--runs=<dir>] [--record=<stage>] [--keep-scratch] [--force] [--no-backup]" >&2
    exit 2
    ;;
  esac
  shift
done
[ -n "${RESTORE_LOCK_SECONDS:-}" ] && RESTORE_INTERNAL_ARGUMENTS+=(--lock-period "${RESTORE_LOCK_SECONDS}s")
[ "${RESTORE_FORCE:-false}" = "true" ] && RESTORE_INTERNAL_ARGUMENTS+=(--force)

case "${RESTORE_INTERNAL_MODE}" in
replace) RESTORE_INTERNAL_VERB="restore" ;;
drill | merge) RESTORE_INTERNAL_VERB="${RESTORE_INTERNAL_MODE}" ;;
*)
  echo "Unknown mode [${RESTORE_INTERNAL_MODE}], taking one of [replace drill merge]" >&2
  exit 2
  ;;
esac

restore_supervised "${RESTORE_INTERNAL_VERB}" "${RESTORE_MODULE_NAME}" --source "${RESTORE_INTERNAL_SOURCE_DIR}" --script "${RESTORE_INTERNAL_SCRIPT}" "${RESTORE_INTERNAL_ARGUMENTS[@]}"