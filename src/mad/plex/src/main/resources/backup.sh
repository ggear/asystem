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
# The run is `supervisor backup run`, this script holds only the module's own hooks. Pruning belongs
# to supervisor's stages, windows are read from its config.json.
# Any variable below can be set on the command line, unless the module's .env already sets it.
#
# BACKUP_SOURCE_PATH      the data path backed up, defaulting to this module's own
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_TIMEOUT_HOURS    the budget a backup waiting on its service allows before abandoning the run
# BACKUP_FORCE_FULL       true to take a full backup where the module would take a delta, set by --full
# BACKUP_SHRINK_PERCENT   the fall in a module's total that marks a run regressed, zero to disable, the module's .env overriding it as PLEX_BACKUP_SHRINK_PERCENT

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="plex"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/plex/latest}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${BACKUP_SOURCE_PATH}")"
BACKUP_SOURCE_VERSION="$(basename "${BACKUP_INTERNAL_SOURCE_DIR}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/backup"
BACKUP_RUN_TIMESTAMP="${BACKUP_RUN_TIMESTAMP:-$(date +"%Y-%m-%d_%H-%M-%S")}"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_VERSIONED_NONE="unversioned"
BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}"
BACKUP_FORCE_FULL="${BACKUP_FORCE_FULL:-false}"
BACKUP_SERVICE_RESTART="${BACKUP_SERVICE_RESTART:-true}"
BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-5}"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${PLEX_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_TARGET_PATH=""
BACKUP_NO_EXCLUDES=()

backup_module() {
  "${BACKUP_SUPERVISOR:-/asystem/bin/supervisor}" backup "${1}" "${BACKUP_MODULE_NAME}" --source "${BACKUP_INTERNAL_SOURCE_DIR}" --run "${BACKUP_RUN_TIMESTAMP}" --state "${BACKUP_STATE_DIR:-}" "${@:2}"
}

backup_target() {
  BACKUP_TARGET_PATH="$(backup_module target "${1:-}" "${2:-}")" || return 1
}

backup_files() {
  local -n backup_files_includes="${2}"
  local -n backup_files_excludes="${3:-BACKUP_NO_EXCLUDES}"
  local arguments=() entry live="PLEX_BACKUP_LIVE"
  for entry in "${backup_files_includes[@]}"; do arguments+=("--include=${entry}"); done
  for entry in "${backup_files_excludes[@]}"; do arguments+=("--exclude=${entry}"); done
  backup_module files --root "${1:-}" --live "${!live:-}" "${arguments[@]}" || return 1
  BACKUP_TARGET_PATH="$(cat "${BACKUP_STATE_DIR}/target")"
}

backup_parent() { backup_module parent --run "${1:-${BACKUP_RUN_TIMESTAMP}}"; }

backup_epoch() { "${BACKUP_SUPERVISOR:-/asystem/bin/supervisor}" backup epoch "${1:-}"; }

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

backup_interrupted() { :; }

backup_completed() { :; }

# The engine owns the run, this snippet owns the backup. `supervisor backup run` checks the throttle, calls
# backup_written, checks the archive's integrity, renames the temporary file on success, writes the manifest and
# sets the exit code, calling this snippet's hooks, each in its own bash. Define backup_written below, naming the
# backup with backup_target (or letting backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". A snippet
# copying files passes backup_files a root under BACKUP_SOURCE_PATH and the names of its include and exclude
# arrays, an absent include fails the backup and whatever under the root neither array covers is reported. A
# snippet leaving the estate changed while it works, such as one stopping its own container, also defines
# backup_interrupted, called on INT, TERM or HUP but never on a backup that merely fails, and backup_completed,
# called once the archive has been named and kept whatever the outcome, whose non-zero return fails the run
# without discarding the archive. A snippet whose service keeps its own store of backups defines
# backup_pruned_store, called after every kept backup. A snippet whose restore depends on its software defines
# backup_versioned, printing that software's version on one line, recorded with the backup so a drill skips a
# point the running software cannot restore, and one whose restore never does prints "${BACKUP_VERSIONED_NONE}".
# No hook may rely on a variable another set. Never assign another wrapper variable, prefix this snippet's own
# state with the module name, and expand a value read from .env as "${VAR:?}", so a missing key fails by name
# rather than corrupting the backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_VERSIONED_NONE   the version backup_versioned prints when the restore does not depend on the software
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

PLEX_BACKUP_CONFIG="config"
PLEX_BACKUP_CONTAINER="${SERVICE_NAME:?}"
PLEX_BACKUP_SERVER="Library/Application Support/Plex Media Server"
PLEX_BACKUP_INCLUDES=(
  "${PLEX_BACKUP_SERVER}/Plug-in Support"
  "${PLEX_BACKUP_SERVER}/Preferences.xml"
)
PLEX_BACKUP_EXCLUDES=(
  "*.db-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
  "Caches"
  "${PLEX_BACKUP_SERVER}/.LocalAdminToken"
  "${PLEX_BACKUP_SERVER}/Cache"
  "${PLEX_BACKUP_SERVER}/Codecs"
  "${PLEX_BACKUP_SERVER}/Crash Reports"
  "${PLEX_BACKUP_SERVER}/Diagnostics"
  "${PLEX_BACKUP_SERVER}/Drivers"
  "${PLEX_BACKUP_SERVER}/Logs"
  "${PLEX_BACKUP_SERVER}/Media"
  "${PLEX_BACKUP_SERVER}/Metadata"
  "${PLEX_BACKUP_SERVER}/Plug-ins"
  "${PLEX_BACKUP_SERVER}/Scanners"
  "${PLEX_BACKUP_SERVER}/Setup Plex.html"
  "${PLEX_BACKUP_SERVER}/Updates"
  "${PLEX_BACKUP_SERVER}/plexmediaserver.pid"
)

PLEX_BACKUP_RESTART_TRIES=5
PLEX_BACKUP_RESTART_WAIT=10

plex_backup_stopped() {
  local reported
  if reported="$(docker stop "${PLEX_BACKUP_CONTAINER}" 2>&1)"; then
    docker wait "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "Stop failed [${PLEX_BACKUP_CONTAINER}] [${reported}], copying the running configuration" >&2
  fi
}

plex_backup_started() {
  [ "${BACKUP_SERVICE_RESTART}" = "true" ] || return 0
  local reported attempt=1
  while :; do
    if reported="$(docker start "${PLEX_BACKUP_CONTAINER}" 2>&1)"; then
      [ "${attempt}" -gt 1 ] && echo "Started [${PLEX_BACKUP_CONTAINER}] on attempt [${attempt}]" >&2
      return 0
    fi
    echo "Start failed [${PLEX_BACKUP_CONTAINER}] [${reported}] on attempt [${attempt}] of [${PLEX_BACKUP_RESTART_TRIES}]" >&2
    [ "${attempt}" -lt "${PLEX_BACKUP_RESTART_TRIES}" ] || break
    attempt=$(( attempt + 1 ))
    sleep "${PLEX_BACKUP_RESTART_WAIT}"
  done
  return 1
}

backup_interrupted() {
  plex_backup_started
}

backup_completed() {
  [ "${BACKUP_SERVICE_RESTART}" = "true" ] || return 0
  [ "$(docker inspect --format '{{.State.Running}}' "${PLEX_BACKUP_CONTAINER}")" = "true" ]
}

backup_versioned() {
  docker exec "${BACKUP_MODULE_NAME}" "/usr/lib/plexmediaserver/Plex Media Server" --version
}

backup_written() {
  local status=0
  plex_backup_stopped
  backup_files "${PLEX_BACKUP_CONFIG}" PLEX_BACKUP_INCLUDES PLEX_BACKUP_EXCLUDES || status=1
  plex_backup_started || true
  return "${status}"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

BACKUP_INTERNAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"

backup_supervised() {
  local container image seconds=$((BACKUP_TIMEOUT_HOURS * 3600 + 7200))
  if [ -x /asystem/bin/supervisor ]; then
    exec /asystem/bin/supervisor backup "$@"
  fi
  container="$(timeout 30 docker ps --filter name=^/supervisor$ --filter status=running --format '{{.Names}}')"
  if [ -n "${container}" ]; then
    exec timeout "${seconds}" docker exec supervisor /asystem/bin/supervisor backup "$@"
  fi
  image="$(timeout 30 docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^supervisor:' | sort -V | tail -n 1)"
  [ -n "${image}" ] || { echo "No supervisor container is running and no supervisor image is installed, cannot run the backup" >&2; exit 1; }
  exec timeout "${seconds}" docker run --rm --init --entrypoint /asystem/bin/supervisor \
    --volume /home/asystem:/home/asystem --volume /var/lib/asystem/install:/var/lib/asystem/install:ro --volume /var/run/docker.sock:/var/run/docker.sock \
    "${image}" backup "$@"
}

case "${1:-}" in
--accept=*)
  backup_supervised accept "${BACKUP_MODULE_NAME}" "${1#--accept=}" --source "${BACKUP_INTERNAL_SOURCE_DIR}"
  ;;
--full)
  BACKUP_FORCE_FULL="true"
  BACKUP_SKIP_HOURS=0
  shift
  ;;
esac

BACKUP_INTERNAL_ARGUMENTS=(--source "${BACKUP_INTERNAL_SOURCE_DIR}" --script "${BACKUP_INTERNAL_SCRIPT}" --skip-period "${BACKUP_SKIP_HOURS}h" --timeout-period "${BACKUP_TIMEOUT_HOURS}h" --shrink-percent "${BACKUP_SHRINK_PERCENT}")
[ "${BACKUP_SERVICE_RESTART}" = "true" ] || BACKUP_INTERNAL_ARGUMENTS+=(--no-restart)
[ "${BACKUP_FORCE_FULL}" = "true" ] && BACKUP_INTERNAL_ARGUMENTS+=(--force-full)
[ -n "${BACKUP_LOCK_SECONDS:-}" ] && BACKUP_INTERNAL_ARGUMENTS+=(--lock-period "${BACKUP_LOCK_SECONDS}s")

backup_supervised run "${BACKUP_MODULE_NAME}" "${BACKUP_INTERNAL_ARGUMENTS[@]}"