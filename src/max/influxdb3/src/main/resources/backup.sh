#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# The wrapper owns the run, the module snippet owns the artifact. The wrapper checks the throttle,
# calls backup_written, renames the temporary file on success, prunes and sets the exit code. The
# snippet defines backup_written, which names its artifact with backup_target (or lets backup_files
# do both) and writes "${BACKUP_PUB_TARGET}.tmp". Nothing else crosses the line: a snippet never
# assigns a wrapper variable, and the wrapper never reads a snippet one.
#
# BACKUP_PUB_*  published by the wrapper for the snippet to read, never assigned by a snippet
# BACKUP_PRI_*  the wrapper's own, read by nothing outside this file
# <MODULE>_*    a snippet's own state, prefixed with its module so it can never collide with either
#
# A snippet needing a value from .env expands it with "${VAR:?}", so a renamed or missing key
# fails by name rather than producing an empty argument and a corrupt artifact.

BACKUP_PRI_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_PRI_ENV}" ] && . "${BACKUP_PRI_ENV}"

BACKUP_PUB_MODULE="influxdb3"
BACKUP_PUB_SOURCE="${SERVICE_DATA_DIR:-/home/asystem/influxdb3/latest}"
BACKUP_PUB_DIR="${BACKUP_PUB_SOURCE}/backup"
BACKUP_PUB_STAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_PUB_FULL="_full"
BACKUP_PUB_DELTA="_delta"
BACKUP_PUB_RETAIN_DAYS="7"
BACKUP_PUB_TARGET=""

BACKUP_PRI_MIN_INTERVAL="3600"
BACKUP_PRI_STATUS=0

backup_target() {
  local suffix="${1:-}" extension="${2:-}"
  if [ -z "${suffix}" ] || [ -z "${extension}" ]; then
    echo "Cannot name the artifact, pass the suffix and the extension to backup_target" >&2
    return 1
  fi
  BACKUP_PUB_TARGET="${BACKUP_PUB_DIR}/${BACKUP_PUB_STAMP}/${BACKUP_PUB_MODULE}_${BACKUP_PUB_STAMP}${suffix}.${extension}"
  mkdir -p "$(dirname "${BACKUP_PUB_TARGET}")"
}

backup_is_full() { [[ "${1}" == *"${BACKUP_PUB_FULL}".* ]]; }

backup_is_delta() { [[ "${1}" == *"${BACKUP_PUB_DELTA}".* ]]; }

backup_discarded() {
  [ -n "${BACKUP_PUB_TARGET}" ] || return 0
  rm -f "${BACKUP_PUB_TARGET}.tmp"
  [ -e "${BACKUP_PUB_TARGET}" ] || rmdir "$(dirname "${BACKUP_PUB_TARGET}")" 2>/dev/null
}

backup_epoch() {
  local stamp="${1: -19}"
  date -d "${stamp:0:10} ${stamp:11:2}:${stamp:14:2}:${stamp:17:2}" +%s 2>/dev/null || echo 0
}

backup_listed() {
  local dir="${1:-${BACKUP_PUB_DIR}}"
  [ -d "${dir}" ] || return 0
  find "${dir}" -maxdepth 1 -mindepth 1 -type d -printf '%f
' 2>/dev/null |
    grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort
}

backup_healthy() {
  local dir="${1:-${BACKUP_PUB_DIR}}" elapsed=3600 names
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 0 ] || return 1
  [ $(($(date +%s) - $(backup_epoch "${names[-1]}"))) -lt $((86400 + elapsed)) ]
}

backup_pruned() {
  local dir="${1:-${BACKUP_PUB_DIR}}" names index cutoff
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 1 ] || return 0
  cutoff=$(($(date +%s) - BACKUP_PUB_RETAIN_DAYS * 86400))
  for ((index = 0; index < ${#names[@]} - 1; index++)); do
    if [ "$(backup_epoch "${names[${index}]}")" -lt "${cutoff}" ]; then
      rm -rf "${dir:?}/${names[${index}]}"
      echo "Deleted backup [${names[${index}]}] older than [${BACKUP_PUB_RETAIN_DAYS}] days"
    fi
  done
}

backup_included() {
  local path
  while IFS= read -r -d ':' path || [ -n "${path}" ]; do
    [ -n "${path}" ] || continue
    if [ -e "${BACKUP_PUB_SOURCE}/${path}" ]; then
      printf '%s
' "${path}"
    else
      echo "Declared path [${path}] is absent from [${BACKUP_PUB_SOURCE}]" >&2
    fi
  done < <(printf '%s:' "${1}")
}

backup_unmatched() {
  local entry path matched includes
  mapfile -t includes < <(backup_included "${1}" 2>/dev/null)
  while IFS= read -r entry; do
    [ "${entry}" = "backup" ] && continue
    matched=""
    for path in "${includes[@]}"; do
      case "${path}" in "${entry}" | "${entry}/"*) matched=1 ;; esac
    done
    [ -n "${matched}" ] || printf '%s
' "${entry}"
  done < <(find "${BACKUP_PUB_SOURCE}" -maxdepth 1 -mindepth 1 -printf '%f
' 2>/dev/null | sort)
}

backup_files() {
  local declared="${1:-}" paths unmatched
  if [ -z "${declared}" ]; then
    echo "Nothing to back up, pass the paths to copy to backup_files" >&2
    return 1
  fi
  mapfile -t paths < <(backup_included "${declared}")
  if [ "${#paths[@]}" -eq 0 ]; then
    echo "No declared path exists under [${BACKUP_PUB_SOURCE}]" >&2
    return 1
  fi
  backup_target "${BACKUP_PUB_FULL}" "${2:-tar.gz}" || return 1
  mapfile -t unmatched < <(backup_unmatched "${declared}")
  [ "${#unmatched[@]}" -gt 0 ] && echo "Not backed up, no declared path covers [${unmatched[*]}]"
  tar --create --directory "${BACKUP_PUB_SOURCE}" --numeric-owner --preserve-permissions     --exclude=backup --file - -- "${paths[@]}" 2>/dev/null | gzip >"${BACKUP_PUB_TARGET}.tmp"
}

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

# Defines backup_written for this module, naming its artifact with backup_target (or letting
# backup_files do both) and writing "${BACKUP_PUB_TARGET}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_PUB_MODULE       this module's name, and its container's name
# BACKUP_PUB_SOURCE       this module's data directory
# BACKUP_PUB_DIR          the backup directory inside it, where artifacts land
# BACKUP_PUB_STAMP        this run's timestamp, shared by the directory and the filename
# BACKUP_PUB_FULL         the suffix marking a self-contained artifact
# BACKUP_PUB_DELTA        the suffix marking an artifact that needs the full before it
# BACKUP_PUB_RETAIN_DAYS  the dense window, in days
# BACKUP_PUB_TARGET       this run's artifact path, empty until backup_target names it

INFLUXDB3_BACKUP_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_BACKUP_STORE="${BACKUP_PUB_SOURCE}/${INFLUXDB3_BACKUP_CLUSTER}/backups"

backup_stored() {
  [ -d "${INFLUXDB3_BACKUP_STORE}" ] || return 0
  find "${INFLUXDB3_BACKUP_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^(full|delta)-[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort -t- -k2
}

backup_status() {
  docker exec --user root "${BACKUP_PUB_MODULE}" influxdb3 status backup --name "$1" --format json 2>/dev/null |
    jq -r '.. | strings | select(test("^(completed|in_progress|failed)$"))' 2>/dev/null | head -1
}

backup_awaited() {
  local status
  while true; do
    status="$(backup_status "$1")"
    [ "${status}" = "completed" ] && return 0
    if [ "${status}" = "failed" ]; then
      echo "Backup failed [$1]" >&2
      return 1
    fi
    sleep 5
  done
}

backup_written() {
  local names parent full name
  mapfile -t names < <(backup_stored)
  parent=""
  full=""
  for name in "${names[@]}"; do
    case "${name}" in full-*) full="${name}" ;; esac
  done
  [ "${#names[@]}" -gt 0 ] && parent="${names[-1]}"
  if [ -n "${full}" ] &&
    [ "$(backup_epoch "${full}")" -ge "$(($(date +%s) - BACKUP_PUB_RETAIN_DAYS * 86400))" ] &&
    [ -n "${parent}" ] && [ "$(backup_status "${parent}")" = "completed" ]; then
    name="delta-${BACKUP_PUB_STAMP}"
    backup_target "${BACKUP_PUB_DELTA}" "tar.gz" || return 1
    echo "Creating a delta backup from parent [${parent}]"
    docker exec --user root "${BACKUP_PUB_MODULE}" \
      influxdb3 create backup --name "${name}" --incremental --parent "${parent}" >/dev/null || return 1
  else
    name="full-${BACKUP_PUB_STAMP}"
    backup_target "${BACKUP_PUB_FULL}" "tar.gz" || return 1
    [ -n "${full}" ] && echo "Starting a new full backup, previous full backup [${full}] is older than [${BACKUP_PUB_RETAIN_DAYS}] days"
    docker exec --user root "${BACKUP_PUB_MODULE}" \
      influxdb3 create backup --name "${name}" >/dev/null || return 1
  fi
  backup_awaited "${name}" || return 1
  tar --create --directory "${INFLUXDB3_BACKUP_STORE}" --file - -- "${name}" 2>/dev/null | gzip >"${BACKUP_PUB_TARGET}.tmp"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

if [ "${1:-}" = "--prune" ]; then
  backup_pruned "${2}"
  exit 0
fi

find "${BACKUP_PUB_DIR}" -type f -name '*.tmp' -delete 2>/dev/null

mapfile -t BACKUP_PRI_EXISTING < <(backup_listed)
if [ "${#BACKUP_PRI_EXISTING[@]}" -gt 0 ]; then
  BACKUP_PRI_AGE=$(($(date +%s) - $(backup_epoch "${BACKUP_PRI_EXISTING[-1]}")))
  if [ "${BACKUP_PRI_AGE}" -lt "${BACKUP_PRI_MIN_INTERVAL}" ]; then
    echo "Backup skipped, newest backup [${BACKUP_PRI_EXISTING[-1]}] is [${BACKUP_PRI_AGE}] seconds old, minimum interval [${BACKUP_PRI_MIN_INTERVAL}] seconds"
    exit 0
  fi
fi

trap backup_discarded EXIT
if backup_written && [ -n "${BACKUP_PUB_TARGET}" ] && [ -s "${BACKUP_PUB_TARGET}.tmp" ]; then
  mv "${BACKUP_PUB_TARGET}.tmp" "${BACKUP_PUB_TARGET}"
  echo "Completed backup [${BACKUP_PUB_MODULE}] to [${BACKUP_PUB_TARGET}]"
  backup_pruned
else
  [ -n "${BACKUP_PUB_TARGET}" ] || echo "Nothing named the artifact, call backup_target in backup_written" >&2
  echo "Failed backup [${BACKUP_PUB_MODULE}]" >&2
  BACKUP_PRI_STATUS=1
fi

find "${BACKUP_PUB_DIR}" -depth -empty -delete -type d
exit "${BACKUP_PRI_STATUS}"