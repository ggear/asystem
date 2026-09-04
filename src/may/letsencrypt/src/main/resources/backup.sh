#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# Usage:
#
#   ./backup.sh              take a backup, full or delta off an eligible parent
#   ./backup.sh --prune      drop local runs older than BACKUP_RETAIN_DAYS, never the newest
#   ./backup.sh --prune-gfs  apply the grandfather-father-son window
#
#   BACKUP_SKIP_HOURS=0 ./backup.sh            take a backup now, whatever the throttle says
#   BACKUP_RETAIN_DAYS=0 ./backup.sh --prune   keep only the newest local run
#
# Both prune forms take the backup root as an optional argument, defaulting to the module's own.
# Any variable below can be set on the command line, unless the module's .env already sets it.
#
# BACKUP_SOURCE_PATH      the data path backed up, defaulting to this module's own
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_KEEP_DAILY       the daily backups kept by --prune-gfs
# BACKUP_KEEP_WEEKLY      the weekly backups kept by --prune-gfs
# BACKUP_KEEP_MONTHLY     the monthly backups kept by --prune-gfs
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_TIMEOUT_HOURS    the budget a backup waiting on its service allows before abandoning the run
# BACKUP_EXCLUDED         the paths deliberately not backed up, declared by the module snippet

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="letsencrypt"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/letsencrypt/latest}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${BACKUP_SOURCE_PATH}")"
BACKUP_SOURCE_VERSION="$(basename "${BACKUP_INTERNAL_SOURCE_DIR}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/backup"
BACKUP_RUN_TIMESTAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-7}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-4}"
BACKUP_KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-12}"
BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}"
BACKUP_EXCLUDED="${BACKUP_EXCLUDED:-}"
BACKUP_SERVICE_RESTART="${BACKUP_SERVICE_RESTART:-true}"
BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-3}"
BACKUP_TARGET_PATH=""

BACKUP_INTERNAL_NEWEST=""
BACKUP_INTERNAL_NEWEST_VERSION=""
BACKUP_INTERNAL_SIZE=0
BACKUP_INTERNAL_STARTED=0
BACKUP_INTERNAL_STATUS=0

backup_target() {
  local suffix="${1:-}" extension="${2:-}"
  if [ -z "${suffix}" ] || [ -z "${extension}" ]; then
    echo "Cannot name the backup, pass the suffix and the extension to backup_target" >&2
    return 1
  fi
  BACKUP_TARGET_PATH="${BACKUP_INTERNAL_ROOT_DIR}/${BACKUP_RUN_TIMESTAMP}/${BACKUP_MODULE_NAME}_at_${BACKUP_RUN_TIMESTAMP}_from_${BACKUP_SOURCE_VERSION}${suffix}.${extension}"
  mkdir -p "$(dirname "${BACKUP_TARGET_PATH}")"
}

backup_is_full() { [[ "${1}" == *"${BACKUP_FULL_SUFFIX}".* ]]; }

backup_is_delta() { [[ "${1}" == *"${BACKUP_DELTA_SUFFIX}".* ]]; }

backup_discarded() {
  [ -n "${BACKUP_TARGET_PATH}" ] || return 0
  rm -f "${BACKUP_TARGET_PATH}.tmp"
  [ -e "${BACKUP_TARGET_PATH}" ] || rmdir "$(dirname "${BACKUP_TARGET_PATH}")" 2>/dev/null
}

backup_epoch() {
  local stamp="${1: -19}"
  date -d "${stamp:0:10} ${stamp:11:2}:${stamp:14:2}:${stamp:17:2}" +%s 2>/dev/null || echo 0
}

backup_listed() {
  local dir="${1:-${BACKUP_INTERNAL_ROOT_DIR}}"
  [ -d "${dir}" ] || return 0
  find "${dir}" -maxdepth 1 -mindepth 1 -type d -printf '%f
' 2>/dev/null |
    grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort
}

backup_versioned() {
  local stamp="${1:-}" dir="${2:-${BACKUP_INTERNAL_ROOT_DIR}}" path name
  [ -n "${stamp}" ] || return 0
  for path in "${dir}/${stamp}"/*; do
    [ -f "${path}" ] || continue
    name="$(basename "${path}")"
    name="${name%"${BACKUP_FULL_SUFFIX}".*}"
    name="${name%"${BACKUP_DELTA_SUFFIX}".*}"
    case "${name}" in
    *_from_*) name="${name##*_from_}" ;;
    *) name="${name#"${BACKUP_MODULE_NAME}_${stamp}_"}" ;;
    esac
    printf '%s
' "${name}"
    return 0
  done
}

backup_healthy() {
  local dir="${1:-${BACKUP_INTERNAL_ROOT_DIR}}" elapsed=3600 names
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 0 ] || return 1
  [ $(($(date +%s) - $(backup_epoch "${names[-1]}"))) -lt $((86400 + elapsed)) ]
}

backup_pruned() {
  local dir="${1:-${BACKUP_INTERNAL_ROOT_DIR}}" names index cutoff
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 1 ] || return 0
  cutoff=$(($(date +%s) - BACKUP_RETAIN_DAYS * 86400))
  for ((index = 0; index < ${#names[@]} - 1; index++)); do
    if [ "$(backup_epoch "${names[${index}]}")" -lt "${cutoff}" ]; then
      rm -rf "${dir:?}/${names[${index}]}"
      echo "Deleted backup [${names[${index}]}] older than [${BACKUP_RETAIN_DAYS}] days"
    fi
  done
}

backup_dir_is_full() {
  local dir="${1}" stamp="${2}" path
  for path in "${dir}/${stamp}"/*; do
    backup_is_full "$(basename "${path}")" && return 0
  done
  return 1
}

backup_pruned_gfs() {
  local dir="${1:-${BACKUP_INTERNAL_ROOT_DIR}}" names name stamp bucket
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 1 ] || return 0
  declare -A keep=() day_seen=()
  local count="${#names[@]}" index day chain
  for ((index = count - 1; index >= 0; index--)); do
    day="${names[${index}]:0:10}"
    if [ -z "${day_seen[${day}]:-}" ]; then
      [ "${#day_seen[@]}" -ge "${BACKUP_KEEP_DAILY}" ] && break
      day_seen["${day}"]=1
    fi
    keep["${names[${index}]}"]=daily
  done
  declare -A week_seen=() month_seen=()
  for ((index = count - 1; index >= 0; index--)); do
    name="${names[${index}]}"
    stamp="${name:0:10}"
    backup_dir_is_full "${dir}" "${name}" || continue
    bucket="$(date -d "${stamp}" +%G-%V 2>/dev/null)"
    if [ -n "${bucket}" ] && [ -z "${week_seen[${bucket}]:-}" ] && [ "${#week_seen[@]}" -lt "${BACKUP_KEEP_WEEKLY}" ]; then
      week_seen["${bucket}"]=1
      keep["${name}"]=weekly
    fi
    bucket="${stamp:0:7}"
    if [ -z "${month_seen[${bucket}]:-}" ] && [ "${#month_seen[@]}" -lt "${BACKUP_KEEP_MONTHLY}" ]; then
      month_seen["${bucket}"]=1
      keep["${name}"]=monthly
    fi
  done
  for ((index = count - 1; index >= 0; index--)); do
    name="${names[${index}]}"
    [ -n "${keep[${name}]:-}" ] || continue
    backup_dir_is_full "${dir}" "${name}" && continue
    for ((chain = index - 1; chain >= 0; chain--)); do
      keep["${names[${chain}]}"]="${keep[${names[${chain}]}]:-chain}"
      backup_dir_is_full "${dir}" "${names[${chain}]}" && break
    done
  done
  for name in "${names[@]}"; do
    if [ -z "${keep[${name}]:-}" ]; then
      rm -rf "${dir:?}/${name}"
      echo "Pruned backup [${name}] outside the grandfather-father-son window"
    fi
  done
}

backup_split() {
  local path
  while IFS= read -r -d ':' path || [ -n "${path}" ]; do
    [ -n "${path}" ] || continue
    printf '%s
' "${path}"
  done < <(printf '%s:' "${1}")
}

backup_included() {
  local path
  while IFS= read -r path; do
    if [ -e "${BACKUP_SOURCE_PATH}/${path}" ]; then
      printf '%s
' "${path}"
    else
      echo "Declared path [${path}] is absent from [${BACKUP_SOURCE_PATH}]" >&2
    fi
  done < <(backup_split "${1}")
}

backup_deepest() {
  local path depth deepest=1
  while IFS= read -r path; do
    depth="$(printf '%s' "${path}" | tr -cd '/' | wc -c)"
    depth=$((depth + 1))
    [ "${depth}" -gt "${deepest}" ] && deepest="${depth}"
  done < <(backup_split "${1}")
  printf '%s
' "${deepest}"
}

backup_unmatched() {
  local entry path state deepest declared reported=() covers=()
  declared="${1}:${BACKUP_EXCLUDED}"
  deepest="$(backup_deepest "${declared}")"
  mapfile -t covers < <(backup_split "${declared}")
  while IFS= read -r entry; do
    [ "${entry}" = "backup" ] && continue
    state="unrelated"
    for path in "${reported[@]}"; do
      case "${entry}" in "${path}/"*) state="beneath" ;; esac
    done
    [ "${state}" = "beneath" ] && continue
    for path in "${covers[@]}"; do
      case "${entry}" in "${path}" | "${path}/"*) state="covered" ;; esac
      [ "${state}" = "covered" ] && break
      case "${path}" in "${entry}/"*) state="ancestor" ;; esac
    done
    [ "${state}" = "unrelated" ] || continue
    printf '%s
' "${entry}"
    reported+=("${entry}")
  done < <(find "${BACKUP_INTERNAL_SOURCE_DIR}" -mindepth 1 -maxdepth "${deepest}" -printf '%P
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
    echo "No declared path exists under [${BACKUP_SOURCE_PATH}]" >&2
    return 1
  fi
  backup_target "${BACKUP_FULL_SUFFIX}" "${2:-tar.gz}" || return 1
  mapfile -t unmatched < <(backup_unmatched "${declared}")
  [ "${#unmatched[@]}" -gt 0 ] && echo "Not backed up and not excluded [${unmatched[*]}]"
  tar --create --directory "${BACKUP_SOURCE_PATH}" --numeric-owner --preserve-permissions     --exclude=backup --file - -- "${paths[@]}" 2>/dev/null | gzip >"${BACKUP_TARGET_PATH}.tmp"
}

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

backup_interrupted() {
  :
}

# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, renames the temporary file on success, prunes and sets the exit code. Define
# backup_written below, naming the backup with backup_target (or letting backup_files do both) and
# writing "${BACKUP_TARGET_PATH}.tmp". A snippet leaving the estate changed while it works, such as
# one stopping its own container, also defines backup_interrupted, called on INT, TERM or HUP but
# never on a backup that merely fails. Declare BACKUP_EXCLUDED as the paths this module deliberately
# does not back up, so backup_files reports only what neither it nor the declaration covers. Never
# assign another wrapper variable, prefix this snippet's own state with the module name, and expand
# a value read from .env as "${VAR:?}", so a missing key fails by name rather than corrupting the
# backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_EXCLUDED         the paths deliberately not backed up, declared by this snippet

LETSENCRYPT_BACKUP_PATHS="letsencrypt/accounts:letsencrypt/archive:letsencrypt/live:letsencrypt/renewal"

BACKUP_EXCLUDED="\
.empty:\
certificates:\
checkalive.sh:\
checkexecuting.sh:\
checkhealthy.sh:\
dnsrobocert:\
letsencrypt/.empty:\
letsencrypt/logs:\
letsencrypt/renewal-hooks:\
letsencrypt/workdir"

backup_written() {
  backup_files "${LETSENCRYPT_BACKUP_PATHS}"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

if [ "${1:-}" = "--prune" ]; then
  backup_pruned "${2}"
  exit 0
fi

if [ "${1:-}" = "--prune-gfs" ]; then
  backup_pruned_gfs "${2}"
  exit 0
fi

find "${BACKUP_INTERNAL_ROOT_DIR}" -type f -name '*.tmp' -delete 2>/dev/null

mapfile -t BACKUP_INTERNAL_EXISTING < <(backup_listed)
if [ "${#BACKUP_INTERNAL_EXISTING[@]}" -gt 0 ]; then
  BACKUP_INTERNAL_NEWEST="${BACKUP_INTERNAL_EXISTING[-1]}"
  BACKUP_INTERNAL_NEWEST_VERSION="$(backup_versioned "${BACKUP_INTERNAL_NEWEST}")"
  BACKUP_INTERNAL_AGE=$(($(date +%s) - $(backup_epoch "${BACKUP_INTERNAL_NEWEST}")))
  if [ "${BACKUP_INTERNAL_AGE}" -lt $((BACKUP_SKIP_HOURS * 3600)) ]; then
    echo "Backup skipped, newest backup [${BACKUP_INTERNAL_NEWEST}] of version [${BACKUP_INTERNAL_NEWEST_VERSION}] is [${BACKUP_INTERNAL_AGE}] seconds old, skipping given within [${BACKUP_SKIP_HOURS}] hours"
    exit 0
  fi
fi

echo "Starting backup from version [${BACKUP_SOURCE_VERSION}] holding [${#BACKUP_INTERNAL_EXISTING[@]}] backups, newest [${BACKUP_INTERNAL_NEWEST:-none}] retaining [${BACKUP_RETAIN_DAYS}] days"

trap backup_discarded EXIT
trap 'backup_interrupted; exit 130' INT
trap 'backup_interrupted; exit 143' TERM
trap 'backup_interrupted; exit 129' HUP
BACKUP_INTERNAL_STARTED=${SECONDS}
if backup_written && [ -n "${BACKUP_TARGET_PATH}" ] && [ -s "${BACKUP_TARGET_PATH}.tmp" ]; then
  mv "${BACKUP_TARGET_PATH}.tmp" "${BACKUP_TARGET_PATH}"
  BACKUP_INTERNAL_SIZE="$(du -m "${BACKUP_TARGET_PATH}" | cut -f1)"
  echo "Finished backup [${BACKUP_INTERNAL_SIZE}] MB in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds to [${BACKUP_TARGET_PATH}]"
  backup_pruned
else
  [ -n "${BACKUP_TARGET_PATH}" ] || echo "Nothing named the backup, call backup_target in backup_written" >&2
  echo "Failed backup in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds" >&2
  BACKUP_INTERNAL_STATUS=1
fi

find "${BACKUP_INTERNAL_ROOT_DIR}" -depth -empty -delete -type d
exit "${BACKUP_INTERNAL_STATUS}"