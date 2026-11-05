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
# BACKUP_SHRINK_PERCENT   the fall in a module's total that marks a run regressed, zero to disable, the module's .env overriding it as ZIGBEE2MQTT_BACKUP_SHRINK_PERCENT

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="zigbee2mqtt"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/zigbee2mqtt/latest}}"
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
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${ZIGBEE2MQTT_BACKUP_SHRINK_PERCENT:-20}}"
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
  local arguments=() entry live="ZIGBEE2MQTT_BACKUP_LIVE"
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

backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "zip" || return 1
  docker exec -i --user root "${BACKUP_MODULE_NAME}" bash -c '
set -o pipefail
response=$(mktemp)
trap "rm -f ${response}" EXIT
for attempt in 1 2 3; do
  transaction="backup-$$-${attempt}"
  mosquitto_sub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/response/backup -C 1 -W 60 >"${response}" 2>/dev/null &
  subscriber=$!
  sleep "${attempt}"
  if mosquitto_pub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/request/backup -m "{\"transaction\":\"${transaction}\"}" 2>/dev/null; then
    wait "${subscriber}" 2>/dev/null
    if [ "$(jq -r --arg transaction "${transaction}" "select(.transaction == \$transaction) | .status // empty" "${response}" 2>/dev/null)" = "ok" ]; then
      jq -r ".data.zip // empty" "${response}" | base64 -d
      exit
    fi
  else
    kill "${subscriber}" 2>/dev/null
    wait "${subscriber}" 2>/dev/null
  fi
  echo "Backup request [${transaction}] got no ok response, attempt [${attempt}/3]" >&2
done
exit 1
  ' >"${BACKUP_TARGET_PATH}.tmp"
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