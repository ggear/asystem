#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

# restore.sh [--mode=replace|merge|drill] [--from=<run>] [--file=<path>] [--runs=<dir>] [--record=<stage>]
#            [--keep-scratch] [--force] [--no-backup]
# Bare is a read-only plan, --force applies it. The run is `supervisor backup restore|drill|merge`, this file holds only
# the module's hooks. merge needs restore_merged, and only a drill after a release runs unprompted.

set -uo pipefail

RESTORE_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${RESTORE_INTERNAL_ENV}" ] && . "${RESTORE_INTERNAL_ENV}"

RESTORE_MODULE_NAME="zigbee2mqtt"
RESTORE_SOURCE_PATH="${RESTORE_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/zigbee2mqtt/latest}}"
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

# The engine (`supervisor backup restore`) owns the run, this snippet owns the restore, as hooks each in its own bash.
# Define restore_applied, writing "${RESTORE_SOURCE_FILE}" back into the service, and declare RESTORE_SERVICE_STATE.
# Optional hooks: restore_planned, restore_staged, restore_sealed, restore_teardown, restore_checked, restore_merged,
# restore_settled.
# No hook relies on a variable another set, own state is prefixed with the module name, .env values expand as "${VAR:?}".
#
# RESTORE_MODULE_NAME     this module's name
# RESTORE_SOURCE_PATH     this module's data path, the restore target
# RESTORE_SOURCE_FILE     the artefact being restored
# RESTORE_CHAIN_FILES     every artefact of the chain, oldest first
# RESTORE_RUN_TIMESTAMP   the timestamp of the run the artefact belongs to
# RESTORE_FULL_SUFFIX     suffix of a full backup
# RESTORE_DELTA_SUFFIX    suffix of a delta backup
# RESTORE_SERVICE_STATE   the state the service must be in, stopped or running
RESTORE_SERVICE_STATE="stopped"

restore_planned() {
  restore_report "would stop [${RESTORE_MODULE_NAME}], unzip the zigbee2mqtt backup into [${RESTORE_SOURCE_PATH}] and start it again"
  restore_report "the coordinator is re-paired from [coordinator_backup.json], the devices themselves are untouched"
}

restore_applied() {
  unzip -o "${RESTORE_SOURCE_FILE}" -d "${RESTORE_SOURCE_PATH}" >/dev/null || {
    restore_fault "could not unzip [${RESTORE_SOURCE_FILE}] into [${RESTORE_SOURCE_PATH}]"
    return 1
  }
  restore_changed "unzipped the zigbee2mqtt backup into [${RESTORE_SOURCE_PATH}]"
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