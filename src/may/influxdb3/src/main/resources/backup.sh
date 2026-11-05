#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# Usage:
#
#   ./backup.sh                 take a backup, full or delta off an eligible parent
#   ./backup.sh --accept=<run>  accept a regressed run, releasing the anchor
#   ./backup.sh --full          take a full backup now, whatever the throttle and the module's own schedule say
#
#   BACKUP_SKIP_HOURS=0 ./backup.sh   take a backup now, whatever the throttle says
#
# The run is the supervisor binary's backup engine, this script holds only the module's own hooks. Pruning belongs
# to supervisor's stages, windows are read from its config.json.
# Any variable below can be set on the command line, unless the module's .env already sets it.
#
# BACKUP_SOURCE_PATH      the data path backed up, defaulting to this module's own
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_TIMEOUT_HOURS    the budget a backup waiting on its service allows before abandoning the run
# BACKUP_FORCE_FULL       true to take a full backup where the module would take a delta, set by --full
# BACKUP_SHRINK_PERCENT   the fall in a module's total that marks a run regressed, zero to disable, the module's .env overriding it as INFLUXDB3_BACKUP_SHRINK_PERCENT

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="influxdb3"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/influxdb3/latest}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${BACKUP_SOURCE_PATH}")"
BACKUP_SOURCE_VERSION="$(basename "${BACKUP_INTERNAL_SOURCE_DIR}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/backup"
BACKUP_RUN_TIMESTAMP="${BACKUP_RUN_TIMESTAMP:-$(date +"%Y-%m-%d_%H-%M-%S")}"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}"
BACKUP_FORCE_FULL="${BACKUP_FORCE_FULL:-false}"
BACKUP_SERVICE_RESTART="${BACKUP_SERVICE_RESTART:-true}"
BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-5}"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${INFLUXDB3_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_TARGET_PATH=""
BACKUP_NO_EXCLUDES=()

backup_engine() {
  "${BACKUP_ENGINE:-/asystem/bin/supervisor}" backup-engine "${1}" --module "${BACKUP_MODULE_NAME}" --source "${BACKUP_INTERNAL_SOURCE_DIR}" --run "${BACKUP_RUN_TIMESTAMP}" --state "${BACKUP_STATE_DIR:-}" "${@:2}"
}

backup_target() {
  BACKUP_TARGET_PATH="$(backup_engine target "${1:-}" "${2:-}")" || return 1
}

backup_files() {
  local -n backup_files_includes="${2}"
  local -n backup_files_excludes="${3:-BACKUP_NO_EXCLUDES}"
  local arguments=() entry live="INFLUXDB3_BACKUP_LIVE"
  for entry in "${backup_files_includes[@]}"; do arguments+=("--include=${entry}"); done
  for entry in "${backup_files_excludes[@]}"; do arguments+=("--exclude=${entry}"); done
  backup_engine files --root "${1:-}" --live "${!live:-}" "${arguments[@]}" || return 1
  BACKUP_TARGET_PATH="$(cat "${BACKUP_STATE_DIR}/target")"
}

backup_parent() { backup_engine parent --run "${1:-${BACKUP_RUN_TIMESTAMP}}"; }

backup_epoch() { backup_engine epoch "${1:-}"; }

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

backup_interrupted() { :; }

backup_completed() { :; }

# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, checks the archive's integrity, renames the temporary file on success, writes the manifest and
# sets the exit code. Define backup_written below, naming the backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". A snippet copying files passes
# backup_files a root under BACKUP_SOURCE_PATH and the names of its include and exclude arrays, an
# absent include fails the backup and whatever under the root neither array covers is reported. A
# snippet leaving the estate changed while it works, such as one stopping its own container, also
# defines backup_interrupted, called on INT, TERM or HUP but never on a backup that merely fails, and
# backup_completed, called once the archive has been named and kept whatever the outcome, whose
# non-zero return fails the run without discarding the archive. A snippet whose service keeps its own
# store of backups defines backup_pruned_store, called after every kept backup. Never assign another wrapper
# variable, prefix this snippet's own state with the module name, and expand a value read from .env
# as "${VAR:?}", so a missing key fails by name rather than corrupting the backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

INFLUXDB3_BACKUP_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_BACKUP_STORE="${BACKUP_SOURCE_PATH}/${INFLUXDB3_BACKUP_CLUSTER}/backups"
INFLUXDB3_BACKUP_AWAIT_SECONDS="${INFLUXDB3_BACKUP_AWAIT_SECONDS:-$((BACKUP_TIMEOUT_HOURS * 3600))}"

backup_stored() {
  [ -d "${INFLUXDB3_BACKUP_STORE}" ] || return 0
  find "${INFLUXDB3_BACKUP_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^(full|delta)-[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort -t- -k2
}

backup_status() {
  docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 status backup --name "$1" |
    awk '/^Status:/ {print $2}' | head -1
}

backup_awaited() {
  local status deadline=$((SECONDS + INFLUXDB3_BACKUP_AWAIT_SECONDS))
  while true; do
    status="$(backup_status "$1")"
    [ "${status}" = "completed" ] && return 0
    if [ "${status}" = "failed" ]; then
      echo "Backup failed [$1]" >&2
      return 1
    fi
    if [ "${INFLUXDB3_BACKUP_AWAIT_SECONDS}" -gt 0 ] && [ "${SECONDS}" -ge "${deadline}" ]; then
      echo "Backup timed out [$1] after [${INFLUXDB3_BACKUP_AWAIT_SECONDS}] seconds holding status [${status:-unknown}]" >&2
      return 1
    fi
    sleep 5
  done
}

backup_eligible() {
  [ -d "${BACKUP_INTERNAL_ROOT_DIR}/${1#*-}" ]
}

backup_pruned_store() {
  local names name live_full dead=() reversed=()
  mapfile -t names < <(backup_stored)
  live_full=""
  for name in "${names[@]}"; do
    case "${name}" in full-*) live_full="${name}" ;; esac
  done
  [ -n "${live_full}" ] || return 0
  local past_full=""
  for name in "${names[@]}"; do
    [ "${name}" = "${live_full}" ] && past_full=1
    [ -n "${past_full}" ] || dead+=("${name}")
  done
  [ "${#dead[@]}" -gt 0 ] || return 0
  for ((name = ${#dead[@]} - 1; name >= 0; name--)); do reversed+=("${dead[name]}"); done
  for name in "${reversed[@]}"; do
    case "${name}" in
    delta-*) docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 delete backup --name "${name}" --incremental >/dev/null 2>&1 || echo "Could not delete dead delta backup [${name}]" >&2 ;;
    esac
  done
  for name in "${dead[@]}"; do
    case "${name}" in
    full-*) docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 delete backup --name "${name}" >/dev/null 2>&1 || echo "Could not delete dead full backup [${name}]" >&2 ;;
    esac
  done
}

backup_fingerprinted() {
  docker exec --user root --interactive "${BACKUP_MODULE_NAME}" bash -s <<'FINGERPRINT'
set -o pipefail
query() {
  influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME:?}" --token "${INFLUXDB3_TOKEN_HOME:?}" "$1"
}
tables="$(query "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox' ORDER BY table_name" | jq -r '.[].table_name')" || exit 1
for table in ${tables}; do
  query "SELECT date_trunc('day', time) AS day, count(*) AS n FROM \"${table}\" WHERE time < date_trunc('day', now()) GROUP BY 1" |
    jq -r --arg table "${table}" '.[] | "\($table)/\(.day[0:10]) \(.n)"' || exit 1
done | sort
FINGERPRINT
}

backup_written() {
  local names parent full name source
  mapfile -t names < <(backup_stored)
  parent=""
  full=""
  for name in "${names[@]}"; do
    backup_eligible "${name}" || continue
    parent="${name}"
    case "${name}" in full-*) full="${name}" ;; esac
  done
  if [ -n "${full}" ] &&
    [ "$(date -d "$(date -d "@$(backup_epoch "${full}")" +%F)" +%G-%V)" = "$(date +%G-%V)" ] &&
    [ -n "${parent}" ] && [ "$(backup_status "${parent}")" = "completed" ] &&
    [ -n "$(backup_parent "${BACKUP_RUN_TIMESTAMP}")" ] && [ "${BACKUP_FORCE_FULL}" != "true" ]; then
    name="delta-${BACKUP_RUN_TIMESTAMP}"
    source="${INFLUXDB3_BACKUP_STORE}/${parent}/incremental"
    backup_target "${BACKUP_DELTA_SUFFIX}" "tar.gz" || return 1
    echo "Creating a delta backup from parent [${parent}]"
    docker exec --user root "${BACKUP_MODULE_NAME}" \
      influxdb3 create backup --name "${name}" --incremental --parent "${parent}" >/dev/null || return 1
  else
    name="full-${BACKUP_RUN_TIMESTAMP}"
    source="${INFLUXDB3_BACKUP_STORE}"
    backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
    if [ "${BACKUP_FORCE_FULL}" = "true" ]; then
      echo "Starting a new full backup as asked, previous full backup [${full:-none}]"
    else
      [ -n "${full}" ] && echo "Starting a new full backup, previous full backup [${full}] is from an earlier ISO week"
    fi
    docker exec --user root "${BACKUP_MODULE_NAME}" \
      influxdb3 create backup --name "${name}" >/dev/null || return 1
  fi
  backup_awaited "${name}" || return 1
  if [ ! -d "${source}/${name}" ]; then
    echo "Backup produced no directory [${source}/${name}]" >&2
    return 1
  fi
  tar --create --directory "${source}" --file - -- "${name}" | gzip >"${BACKUP_TARGET_PATH}.tmp"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

BACKUP_INTERNAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
BACKUP_INTERNAL_VARIABLES=(BACKUP_MODULE_NAME BACKUP_SOURCE_PATH BACKUP_INTERNAL_SOURCE_DIR BACKUP_SKIP_HOURS BACKUP_FORCE_FULL BACKUP_SERVICE_RESTART BACKUP_TIMEOUT_HOURS BACKUP_SHRINK_PERCENT BACKUP_LOCK_WAIT)

backup_engine_executed() {
  local verb="${1}" variable arguments=() container image
  shift
  BACKUP_SCRIPT="${BACKUP_INTERNAL_SCRIPT}"
  if [ -x /asystem/bin/supervisor ]; then
    for variable in "${BACKUP_INTERNAL_VARIABLES[@]}" BACKUP_SCRIPT; do [ -n "${!variable+x}" ] && export "${variable?}"; done
    exec /asystem/bin/supervisor backup-engine "${verb}" "$@"
  fi
  for variable in "${BACKUP_INTERNAL_VARIABLES[@]}" BACKUP_SCRIPT; do
    [ -n "${!variable+x}" ] && arguments+=(--env "${variable}=${!variable}")
  done
  container="$(timeout 30 docker ps --filter name=^/supervisor$ --filter status=running --format '{{.Names}}')"
  if [ -n "${container}" ]; then
    exec timeout "$((BACKUP_TIMEOUT_HOURS * 3600 + 7200))" docker exec "${arguments[@]}" supervisor /asystem/bin/supervisor backup-engine "${verb}" "$@"
  fi
  image="$(timeout 30 docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^supervisor:' | sort -V | tail -n 1)"
  [ -n "${image}" ] || { echo "No supervisor container is running and no supervisor image is installed, cannot run the backup engine" >&2; exit 1; }
  exec timeout "$((BACKUP_TIMEOUT_HOURS * 3600 + 7200))" docker run --rm --init --entrypoint /asystem/bin/supervisor "${arguments[@]}" \
    --volume /home/asystem:/home/asystem --volume /var/lib/asystem/install:/var/lib/asystem/install:ro --volume /var/run/docker.sock:/var/run/docker.sock \
    "${image}" backup-engine "${verb}" "$@"
}

case "${1:-}" in
--accept=*)
  backup_engine_executed accept "${BACKUP_INTERNAL_SOURCE_DIR}" "${1#--accept=}"
  ;;
--full)
  BACKUP_FORCE_FULL="true"
  BACKUP_SKIP_HOURS=0
  shift
  ;;
esac

backup_engine_executed run