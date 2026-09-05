#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

#   restore.sh [--force] [--from=<timestamp>] [--file=<path>] [--no-backup]
#
#   bare      read only, resolves the artifact and prints the plan, changes nothing
#   --force   applies the plan, the only destructive form
#
#   from      the run to restore, a backup timestamp, defaulting to the newest run
#   file      an artifact path outright, for one lifted off the share or elsewhere
#   no-backup skip the safety backup taken of the current data before applying
#
# Applying refuses unless all of these hold:
#
#   1. An artifact resolves, from the newest run or the one named by 'from' or 'file'
#   2. The artifact is readable and its compression integrity check passes
#   3. The module's snippet defines restore_applied
#   4. The safety backup of the current data succeeds, unless 'no-backup' is given
#   5. The param 'force' is given, otherwise the plan is printed and nothing changes
#
# It is never run by install.sh, fab or the supervisor backup stages, only by hand.

set -uo pipefail

RESTORE_FORCE="${RESTORE_FORCE:-false}"
RESTORE_BACKUP="${RESTORE_BACKUP:-true}"
RESTORE_FROM=""
RESTORE_FILE=""
RESTORE_FAULTS=0
RESTORE_CHANGED=0

while [ "$#" -gt 0 ]; do
  case "$1" in
  --force) RESTORE_FORCE="true" ;;
  --no-backup) RESTORE_BACKUP="false" ;;
  --from=*) RESTORE_FROM="${1#--from=}" ;;
  --from)
    shift
    RESTORE_FROM="${1:-}"
    ;;
  --file=*) RESTORE_FILE="${1#--file=}" ;;
  --file)
    shift
    RESTORE_FILE="${1:-}"
    ;;
  *)
    echo "Usage: ${0} [--force] [--from=<timestamp>] [--file=<path>] [--no-backup]" >&2
    exit 2
    ;;
  esac
  shift
done

RESTORE_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${RESTORE_INTERNAL_ENV}" ] && . "${RESTORE_INTERNAL_ENV}"

RESTORE_MODULE_NAME="influxdb3"
RESTORE_SOURCE_PATH="${RESTORE_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/influxdb3/latest}}"
RESTORE_INTERNAL_SOURCE_DIR="$(readlink -f "${RESTORE_SOURCE_PATH}")"
RESTORE_INTERNAL_ROOT_DIR="$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")/backup"
RESTORE_INTERNAL_BACKUP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup.sh"
RESTORE_FULL_SUFFIX="_full"
RESTORE_DELTA_SUFFIX="_delta"
RESTORE_SERVICE_STATE="stopped"
RESTORE_SOURCE_FILE=""
RESTORE_SOURCE_VERSION=""
RESTORE_RUN_TIMESTAMP=""
RESTORE_INTERNAL_KIND="unknown"
RESTORE_INTERNAL_RESTARTED="false"

restore_fault() {
  echo "❌ $*" >&2
  RESTORE_FAULTS=$((RESTORE_FAULTS + 1))
}

restore_report() { echo "   $*"; }

restore_changed() {
  echo "   $*"
  RESTORE_CHANGED=$((RESTORE_CHANGED + 1))
}

restore_forced() {
  [ "${RESTORE_FORCE}" = "true" ] && return 0
  restore_fault "refusing to $* without [--force]"
  return 1
}

restore_listed() {
  [ -d "${RESTORE_INTERNAL_ROOT_DIR}" ] || return 0
  find "${RESTORE_INTERNAL_ROOT_DIR}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort
}

restore_versioned() {
  local name="${1:-}" stem
  stem="${name%"${RESTORE_FULL_SUFFIX}".*}"
  stem="${stem%"${RESTORE_DELTA_SUFFIX}".*}"
  case "${stem}" in
  *_from_*) printf '%s\n' "${stem##*_from_}" ;;
  *) printf '%s\n' "${stem#"${RESTORE_MODULE_NAME}_${RESTORE_RUN_TIMESTAMP}_"}" ;;
  esac
}

restore_resolved() {
  local names name
  if [ -n "${RESTORE_FILE}" ]; then
    [ -f "${RESTORE_FILE}" ] || { restore_fault "no artifact at [${RESTORE_FILE}]"; return 1; }
    RESTORE_SOURCE_FILE="${RESTORE_FILE}"
    RESTORE_RUN_TIMESTAMP="$(basename "$(dirname "${RESTORE_SOURCE_FILE}")")"
  else
    if [ -n "${RESTORE_FROM}" ]; then
      RESTORE_RUN_TIMESTAMP="${RESTORE_FROM}"
    else
      mapfile -t names < <(restore_listed)
      [ "${#names[@]}" -gt 0 ] || { restore_fault "no backup runs under [${RESTORE_INTERNAL_ROOT_DIR}]"; return 1; }
      RESTORE_RUN_TIMESTAMP="${names[-1]}"
    fi
    [ -d "${RESTORE_INTERNAL_ROOT_DIR}/${RESTORE_RUN_TIMESTAMP}" ] ||
      { restore_fault "no backup run [${RESTORE_RUN_TIMESTAMP}] under [${RESTORE_INTERNAL_ROOT_DIR}]"; return 1; }
    for name in "${RESTORE_INTERNAL_ROOT_DIR}/${RESTORE_RUN_TIMESTAMP}"/*; do
      [ -f "${name}" ] || continue
      RESTORE_SOURCE_FILE="${name}"
      break
    done
    [ -n "${RESTORE_SOURCE_FILE}" ] ||
      { restore_fault "no artifact in run [${RESTORE_RUN_TIMESTAMP}]"; return 1; }
  fi
  name="$(basename "${RESTORE_SOURCE_FILE}")"
  RESTORE_SOURCE_VERSION="$(restore_versioned "${name}")"
  case "${name}" in
  *"${RESTORE_DELTA_SUFFIX}".*) RESTORE_INTERNAL_KIND="delta" ;;
  *"${RESTORE_FULL_SUFFIX}".*) RESTORE_INTERNAL_KIND="full" ;;
  esac
}

restore_intact() {
  case "${RESTORE_SOURCE_FILE}" in
  *.gz) gzip -t "${RESTORE_SOURCE_FILE}" 2>/dev/null ;;
  *.zip) unzip -t "${RESTORE_SOURCE_FILE}" >/dev/null 2>&1 ;;
  *) return 0 ;;
  esac
}

restore_files() {
  local declared="${1:-}" target="${2:-${RESTORE_SOURCE_PATH}}"
  [ -d "${target}" ] || { restore_fault "no restore target [${target}]"; return 1; }
  tar --extract --directory "${target}" --numeric-owner --preserve-permissions \
    --file - <"${RESTORE_SOURCE_FILE}" 2>/dev/null ||
    tar --extract --gzip --directory "${target}" --numeric-owner --preserve-permissions \
      --file "${RESTORE_SOURCE_FILE}" || {
    restore_fault "could not extract [${RESTORE_SOURCE_FILE}] into [${target}]"
    return 1
  }
  restore_changed "extracted [${declared:-archive}] into [${target}]"
}

restore_backed() {
  [ "${RESTORE_BACKUP}" = "true" ] || { restore_report "skipping the safety backup, [--no-backup] given"; return 0; }
  [ -f "${RESTORE_INTERNAL_BACKUP}" ] || { restore_report "skipping the safety backup, no [backup.sh] beside this script"; return 0; }
  restore_report "taking a safety backup of the current data first ..."
  BACKUP_SKIP_HOURS=0 BACKUP_SERVICE_RESTART=false bash "${RESTORE_INTERNAL_BACKUP}" || {
    restore_fault "the safety backup failed, abandoning the restore"
    return 1
  }
  RESTORE_CHANGED=$((RESTORE_CHANGED + 1))
}

restore_stopped() {
  docker ps --format '{{.Names}}' | grep -Fxq "${RESTORE_MODULE_NAME}" || return 0
  docker stop "${RESTORE_MODULE_NAME}" >/dev/null 2>&1 || { restore_fault "could not stop [${RESTORE_MODULE_NAME}]"; return 1; }
  RESTORE_INTERNAL_RESTARTED="true"
  restore_changed "stopped [${RESTORE_MODULE_NAME}]"
}

restore_started() {
  [ "${RESTORE_INTERNAL_RESTARTED}" = "true" ] || return 0
  docker start "${RESTORE_MODULE_NAME}" >/dev/null 2>&1 || { restore_fault "could not start [${RESTORE_MODULE_NAME}]"; return 1; }
  restore_changed "started [${RESTORE_MODULE_NAME}]"
}

restore_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "${RESTORE_MODULE_NAME}" && return 0
  restore_fault "[${RESTORE_MODULE_NAME}] must be running to restore, start it first"
  return 1
}

restore_planned() {
  restore_report "would apply [${RESTORE_SOURCE_FILE}] into [${RESTORE_SOURCE_PATH}]"
}

restore_applied() {
  restore_fault "nothing to restore, define restore_applied in the module snippet"
  return 1
}

# The wrapper owns the run, this snippet owns the restore. The wrapper resolves the artifact, checks
# its integrity, takes a safety backup, stops or starts the service and sets the exit code. Define
# restore_applied below, reading "${RESTORE_SOURCE_FILE}" and writing it back into the service, and
# optionally restore_planned to describe that in the dry run. Declare RESTORE_SERVICE_STATE as
# "stopped" when the restore replaces files the service holds open, or "running" when it is applied
# through the service itself. Never assign another wrapper variable, prefix this snippet's own state
# with the module name, and expand a value read from .env as "${VAR:?}", so a missing key fails by
# name rather than corrupting the restore.
#
# RESTORE_MODULE_NAME     this module's name
# RESTORE_SOURCE_PATH     this module's data path, the restore target
# RESTORE_SOURCE_FILE     the artifact being restored from
# RESTORE_SOURCE_VERSION  the version the artifact was taken from
# RESTORE_RUN_TIMESTAMP   the timestamp of the run the artifact belongs to
# RESTORE_FULL_SUFFIX     the file suffix marking a full backup
# RESTORE_DELTA_SUFFIX    the file suffix marking a delta backup
# RESTORE_SERVICE_STATE   the state the service must be in, stopped or running
RESTORE_SERVICE_STATE="running"

INFLUXDB3_RESTORE_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_RESTORE_STORE="${RESTORE_SOURCE_PATH}/${INFLUXDB3_RESTORE_CLUSTER}/backups"

influxdb3_restore_named() {
  local root
  root="$(tar -tzf "${RESTORE_SOURCE_FILE}" 2>/dev/null | head -1)"
  printf '%s\n' "${root%%/*}"
}

influxdb3_restore_parent() {
  local fulls
  mapfile -t fulls < <(find "${INFLUXDB3_RESTORE_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^full-' | sort)
  [ "${#fulls[@]}" -eq 1 ] || return 1
  printf '%s\n' "${fulls[0]}"
}

restore_planned() {
  local name parent
  name="$(influxdb3_restore_named)"
  case "${name}" in
  delta-*)
    parent="$(influxdb3_restore_parent)" || {
      restore_report "would need exactly one full backup already in [${INFLUXDB3_RESTORE_STORE}] to place [${name}] under, restore its full first"
      return 0
    }
    restore_report "would extract [${name}] into [${INFLUXDB3_RESTORE_STORE}/${parent}/incremental] and run [influxdb3 create restore --backup ${name}]"
    ;;
  *)
    restore_report "would extract [${name}] into [${INFLUXDB3_RESTORE_STORE}] and run [influxdb3 create restore --backup ${name}]"
    ;;
  esac
}

restore_applied() {
  local name parent target
  name="$(influxdb3_restore_named)"
  [ -n "${name}" ] || { restore_fault "could not read the backup name out of [${RESTORE_SOURCE_FILE}]"; return 1; }
  case "${name}" in
  delta-*)
    parent="$(influxdb3_restore_parent)" || {
      restore_fault "need exactly one full backup in [${INFLUXDB3_RESTORE_STORE}] to place [${name}] under, restore its full first"
      return 1
    }
    target="${INFLUXDB3_RESTORE_STORE}/${parent}/incremental"
    ;;
  *) target="${INFLUXDB3_RESTORE_STORE}" ;;
  esac
  mkdir -p "${target}"
  tar --extract --gzip --directory "${target}" --file "${RESTORE_SOURCE_FILE}" || {
    restore_fault "could not extract [${RESTORE_SOURCE_FILE}] into [${target}]"
    return 1
  }
  restore_changed "extracted [${name}] into [${target}]"
  docker exec --user root "${RESTORE_MODULE_NAME}" influxdb3 create restore --backup "${name}" || {
    restore_fault "could not restore [${name}] into [${RESTORE_MODULE_NAME}]"
    return 1
  }
  restore_changed "restored [${name}] into [${RESTORE_MODULE_NAME}]"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

echo && echo "Restore $([ "${RESTORE_FORCE}" = "true" ] && echo apply || echo plan) [${RESTORE_MODULE_NAME}] against [${RESTORE_SOURCE_PATH}] forced [${RESTORE_FORCE}]" && echo
if ! restore_resolved; then
  echo && echo "❌ Restore found [${RESTORE_FAULTS}] fault(s), changed [${RESTORE_CHANGED}]" && echo
  exit 1
fi
restore_report "artifact  [${RESTORE_SOURCE_FILE}]"
restore_report "taken     [${RESTORE_RUN_TIMESTAMP}] from version [${RESTORE_SOURCE_VERSION:-unknown}] kind [${RESTORE_INTERNAL_KIND}]"
restore_report "size      [$(du -m -s "${RESTORE_SOURCE_FILE}" 2>/dev/null | cut -f1)] MB"
restore_report "service   must be [${RESTORE_SERVICE_STATE}]"
if ! restore_intact; then
  restore_fault "the artifact failed its integrity check [${RESTORE_SOURCE_FILE}]"
  echo && echo "❌ Restore found [${RESTORE_FAULTS}] fault(s), changed [${RESTORE_CHANGED}]" && echo
  exit 1
fi
restore_report "integrity passed"
echo
if [ "${RESTORE_FORCE}" != "true" ]; then
  restore_planned
  echo && echo "✅ Restore plan resolved, rerun with [--force] to apply, changed [${RESTORE_CHANGED}]" && echo
  exit 0
fi
if restore_backed; then
  if [ "${RESTORE_SERVICE_STATE}" = "running" ]; then
    restore_running && restore_applied
  else
    restore_stopped && restore_applied
    restore_started
  fi
fi
echo
if [ "${RESTORE_FAULTS}" -ne 0 ]; then
  echo "❌ Restore found [${RESTORE_FAULTS}] fault(s), changed [${RESTORE_CHANGED}]" && echo
  exit 1
fi
echo "✅ Restore applied from [${RESTORE_RUN_TIMESTAMP}], changed [${RESTORE_CHANGED}]" && echo