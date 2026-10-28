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
#   ./backup.sh --accept=<run>  accept a regressed run, releasing the anchor
#
#   BACKUP_SKIP_HOURS=0 ./backup.sh            take a backup now, whatever the throttle says
#   BACKUP_RETAIN_DAYS=0 ./backup.sh --prune   keep only the newest local run
#
# Both prune forms take the backup root as an optional argument, defaulting to the module's own.
# Any variable below can be set on the command line, unless the module's .env already sets it.
#
# BACKUP_SOURCE_PATH      the data path backed up, defaulting to this module's own
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_KEEP_DAILY       the daily backups kept by --prune-gfs, the module's .env overriding it as ZIGBEE2MQTT_BACKUP_KEEP_DAILY
# BACKUP_KEEP_WEEKLY      the weekly backups kept by --prune-gfs, the module's .env overriding it as ZIGBEE2MQTT_BACKUP_KEEP_WEEKLY
# BACKUP_KEEP_MONTHLY     the monthly backups kept by --prune-gfs, the module's .env overriding it as ZIGBEE2MQTT_BACKUP_KEEP_MONTHLY
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_TIMEOUT_HOURS    the budget a backup waiting on its service allows before abandoning the run

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="zigbee2mqtt"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/zigbee2mqtt/latest}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${BACKUP_SOURCE_PATH}")"
BACKUP_SOURCE_VERSION="$(basename "${BACKUP_INTERNAL_SOURCE_DIR}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/backup"
BACKUP_RUN_TIMESTAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-${ZIGBEE2MQTT_BACKUP_KEEP_DAILY:-7}}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-${ZIGBEE2MQTT_BACKUP_KEEP_WEEKLY:-4}}"
BACKUP_KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-${ZIGBEE2MQTT_BACKUP_KEEP_MONTHLY:-12}}"
BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}"
BACKUP_SERVICE_RESTART="${BACKUP_SERVICE_RESTART:-true}"
BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-5}"
BACKUP_TARGET_PATH=""

BACKUP_INTERNAL_NEWEST=""
BACKUP_INTERNAL_NEWEST_VERSION=""
BACKUP_INTERNAL_SIZE=0
BACKUP_INTERNAL_STARTED=0
BACKUP_INTERNAL_STATUS=0
BACKUP_INTERNAL_WRITTEN="false"
BACKUP_INTERNAL_VERIFIER=""

backup_target() {
  local suffix="${1:-}" extension="${2:-}"
  if [ -z "${suffix}" ] || [ -z "${extension}" ]; then
    echo "Cannot name the backup, pass the suffix and the extension to backup_target" >&2
    return 1
  fi
  if [ "${suffix}" = "${BACKUP_DELTA_SUFFIX}" ] && [ -z "$(backup_parent "${BACKUP_RUN_TIMESTAMP}")" ]; then
    echo "Cannot write a delta, no full backup is held locally for it to hang off" >&2
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
    case "${name}" in *"${BACKUP_FULL_SUFFIX}".* | *"${BACKUP_DELTA_SUFFIX}".*) ;; *) continue ;; esac
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
      backup_removed "${dir}" "${names[${index}]}" "older than [${BACKUP_RETAIN_DAYS}] days" window
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

backup_gfs_kept() {
  local dir="${1}" daily="${2}" weekly="${3}" monthly="${4}" names name stamp bucket
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 0 ] || return 0
  declare -A keep=() day_seen=()
  local count="${#names[@]}" index day chain
  for ((index = count - 1; index >= 0; index--)); do
    day="${names[${index}]:0:10}"
    if [ -z "${day_seen[${day}]:-}" ]; then
      [ "${#day_seen[@]}" -ge "${daily}" ] && break
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
    if [ -n "${bucket}" ] && [ -z "${week_seen[${bucket}]:-}" ] && [ "${#week_seen[@]}" -lt "${weekly}" ]; then
      week_seen["${bucket}"]=1
      keep["${name}"]=weekly
    fi
    bucket="${stamp:0:7}"
    if [ -z "${month_seen[${bucket}]:-}" ] && [ "${#month_seen[@]}" -lt "${monthly}" ]; then
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
    [ -n "${keep[${name}]:-}" ] && echo "${name}"
  done
}

backup_pruned_gfs() {
  local dir="${1:-${BACKUP_INTERNAL_ROOT_DIR}}" names name kept
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 1 ] || return 0
  kept="$(backup_gfs_kept "${dir}" "${BACKUP_KEEP_DAILY}" "${BACKUP_KEEP_WEEKLY}" "${BACKUP_KEEP_MONTHLY}")"
  for name in "${names[@]}"; do
    grep -Fxq -- "${name}" <<<"${kept}" || backup_removed "${dir}" "${name}" "outside the grandfather-father-son window" gfs
  done
}

backup_files() {
  local root="${1:-}" dir path entry depth deepest=1 covered live attempts attempt status paths=() excludes=() excluded=() missing=() unmatched=()
  if [ -z "${root}" ] || [ -z "${2:-}" ]; then
    echo "Nothing to back up, pass the root and the name of the include array to backup_files" >&2
    return 1
  fi
  local -n backup_files_includes="${2}"
  paths=("${backup_files_includes[@]}")
  BACKUP_FINGERPRINT_INCLUDES=("${backup_files_includes[@]}")
  if [ -n "${3:-}" ]; then
    local -n backup_files_excludes="${3}"
    excludes=("${backup_files_excludes[@]}")
  fi
  if [ "${#paths[@]}" -eq 0 ]; then
    echo "Nothing to back up, the include array [${2}] is empty" >&2
    return 1
  fi
  dir="${BACKUP_INTERNAL_SOURCE_DIR}/${root}"
  for path in "${paths[@]}"; do
    [ -e "${dir}/${path}" ] || missing+=("${path}")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    echo "Declared paths [${missing[*]}] are absent from [${dir}]" >&2
    return 1
  fi
  for path in "${paths[@]}" "${excludes[@]}"; do
    depth="$(printf '%s' "${path}" | tr -cd '/' | wc -c)"
    depth=$((depth + 1))
    [ "${depth}" -gt "${deepest}" ] && deepest="${depth}"
  done
  while IFS= read -r entry; do
    [ "${entry}" = "backup" ] && continue
    covered="false"
    for path in "${unmatched[@]}"; do
      case "${entry}" in "${path}/"*) covered="true" ;; esac
    done
    for path in "${paths[@]}"; do
      case "${entry}" in "${path}" | "${path}/"*) covered="true" ;; esac
      case "${path}" in "${entry}/"*) covered="true" ;; esac
    done
    for path in "${excludes[@]}"; do
      # shellcheck disable=SC2254
      case "${entry}" in ${path} | */${path} | ${path}/* | */${path}/*) covered="true" ;; esac
      case "${path}" in "${entry}/"*) covered="true" ;; esac
    done
    [ "${covered}" = "true" ] || unmatched+=("${entry}")
  done < <(find "${dir}" -mindepth 1 -maxdepth "${deepest}" -printf '%P
' 2>/dev/null | sort)
  backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
  [ "${#unmatched[@]}" -gt 0 ] && echo "Not backed up and not excluded [${unmatched[*]}]"
  excluded=(--exclude=backup)
  for path in "${excludes[@]}"; do
    excluded+=("--exclude=${path}")
  done
  live="${BACKUP_MODULE_NAME^^}_BACKUP_LIVE"
  attempts=1
  [ "${!live:-}" = "atomic" ] && attempts=3
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    status=0
    tar --create --directory "${dir}" --numeric-owner --preserve-permissions       "${excluded[@]}" --file - -- "${paths[@]}" | gzip >"${BACKUP_TARGET_PATH}.tmp" || status="${PIPESTATUS[0]}"
    [ "${status}" -ne 1 ] && break
    [ "${attempt}" -lt "${attempts}" ] || break
    echo "Archive changed while being read, retrying attempt [${attempt}] of [${attempts}]" >&2
    sleep 10
  done
  return "${status}"
}

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

backup_interrupted() {
  :
}

backup_completed() {
  :
}

# shellcheck shell=bash
# shellcheck disable=SC2034

BACKUP_FINGERPRINT_INCLUDES=()

backup_fingerprinted_default() {
  local file="${1:-}" includes
  includes="$(
    IFS=:
    echo "${BACKUP_FINGERPRINT_INCLUDES[*]}"
  )"
  case "${file}" in
  *.sql.gz)
    gzip -dc "${file}" | awk '
      /^\\connect / { db = $2; gsub(/["]/, "", db); next }
      /^-- Current Database: / { mdb = $4; gsub(/[`]/, "", mdb); next }
      /^COPY / { unit = db "." $2; incopy = 1; rows[unit] += 0; order[unit] = 1; next }
      /^\\\.$/ { incopy = 0; next }
      incopy { rows[unit]++; next }
      mdb != "" { bytes[mdb] += length($0) + 1 }
      END {
        for (unit in rows) print unit, rows[unit]
        for (unit in bytes) print unit, bytes[unit]
      }' | sort
    ;;
  *.tar.gz)
    tar -tvzf "${file}" | awk -v includes="${includes}" '
      BEGIN { count = split(includes, wanted, ":") }
      {
        gnu = ($2 ~ /\//)
        size = gnu ? $3 : $5
        skip = gnu ? 5 : 8
        name = $0
        sub(/^ +/, "", name)
        for (field = 0; field < skip; field++) sub(/^[^ ]+ +/, "", name)
        sub(/ -> .*$/, "", name)
        sub(/^\.\//, "", name)
        if (substr($1, 1, 1) == "d" || name == "") next
        unit = ""
        for (index_ = 1; index_ <= count; index_++) {
          if (wanted[index_] != "" && (name == wanted[index_] || index(name, wanted[index_] "/") == 1)) { unit = wanted[index_]; break }
        }
        if (unit == "") { unit = name; sub(/\/.*$/, "", unit) }
        bytes[unit] += size
      }
      END { for (unit in bytes) print unit, bytes[unit] }' | sort
    ;;
  *.zip)
    unzip -l "${file}" | awk '
      NR > 3 && $1 ~ /^[0-9]+$/ && $4 != "" {
        name = $0
        sub(/^ *[0-9]+ +[^ ]+ +[^ ]+ +/, "", name)
        bytes[name] += $1
      }
      END { for (unit in bytes) print unit, bytes[unit] }' | sort
    ;;
  esac
}

# shellcheck shell=bash

asystem_locked() {
  local module="${1}" parent="${2}" wait="${3:-300}" file
  [ "${ASYSTEM_LOCK_HELD:-}" = "${module}" ] && return 0
  command -v flock >/dev/null 2>&1 || return 0
  file="${parent}/.lock"
  mkdir -p "${parent}" 2>/dev/null || return 0
  exec 9>"${file}" || return 0
  flock -w "${wait}" 9 || {
    echo "Another actor holds the lock for [${module}] at [${file}], giving up after [${wait}] seconds" >&2
    return 1
  }
  export ASYSTEM_LOCK_HELD="${module}"
}

# shellcheck shell=bash
# shellcheck disable=SC2034

# Mirrors metric.BackupState<Name> in supervisor internal/metric/metric_schema.go, which owns the words, as BACKUP_STATE_<NAME>. A supervisor test holds the two equal.
BACKUP_STATE_SUCCESS="success"
BACKUP_STATE_REGRESSED="regressed"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${ZIGBEE2MQTT_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_EVIDENCE_LIMIT=20
BACKUP_MANIFEST_LEAF="manifest.json"

backup_fingerprinted() {
  backup_fingerprinted_default "$@"
}

backup_durable() {
  return 0
}

backup_manifest_path() {
  printf '%s\n' "${BACKUP_INTERNAL_ROOT_DIR}/${1}/.meta/${BACKUP_MANIFEST_LEAF}"
}

backup_manifest_field() {
  local path
  path="$(backup_manifest_path "${1}")"
  [ -f "${path}" ] || return 0
  sed -n 's/^  "'"${2}"'": "\{0,1\}\([^",]*\)"\{0,1\},\{0,1\}$/\1/p' "${path}" | head -n 1
}

backup_manifest_fingerprint() {
  local path
  path="$(backup_manifest_path "${1}")"
  [ -f "${path}" ] || return 0
  awk '/^  "fingerprint": \{$/ { inside = 1; next } inside && /^  \}/ { exit } inside { print }' "${path}" |
    sed 's/^    "\(.*\)": \([0-9]*\),\{0,1\}$/\1 \2/' | sort
}

backup_json_text() {
  local text="${1:-}"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  printf '%s' "${text}"
}

backup_previous() {
  local run="${1}" names index
  mapfile -t names < <(backup_listed)
  for ((index = ${#names[@]} - 1; index >= 0; index--)); do
    [ "${names[index]}" \< "${run}" ] || continue
    [ -n "$(ls "${BACKUP_INTERNAL_ROOT_DIR}/${names[index]}"/*"${BACKUP_FULL_SUFFIX}".* "${BACKUP_INTERNAL_ROOT_DIR}/${names[index]}"/*"${BACKUP_DELTA_SUFFIX}".* 2>/dev/null)" ] || continue
    printf '%s\n' "${names[index]}"
    return 0
  done
}

backup_parent() {
  local run="${1}" names index
  mapfile -t names < <(backup_listed)
  for ((index = ${#names[@]} - 1; index >= 0; index--)); do
    [ "${names[index]}" \< "${run}" ] || continue
    backup_dir_is_full "${BACKUP_INTERNAL_ROOT_DIR}" "${names[index]}" && {
      printf '%s\n' "${names[index]}"
      return 0
    }
  done
}

backup_baseline() {
  local run="${1}" names index
  mapfile -t names < <(backup_listed)
  for ((index = ${#names[@]} - 1; index >= 0; index--)); do
    [ "${names[index]}" \< "${run}" ] || continue
    [ "$(backup_manifest_field "${names[index]}" verdict)" = "${BACKUP_STATE_SUCCESS}" ] || continue
    [ -n "$(backup_manifest_fingerprint "${names[index]}")" ] || continue
    printf '%s\n' "${names[index]}"
    return 0
  done
}

backup_regression() {
  local current="${1}" baseline="${2}" unit count was now=0 base=0 absent=0 shown=0 first="" percent
  BACKUP_INTERNAL_VERDICT="${BACKUP_STATE_SUCCESS}"
  BACKUP_INTERNAL_EVIDENCE=()
  [ -n "${baseline}" ] || return 0
  declare -A have=()
  while read -r line; do
    [ -n "${line}" ] && have["${line% *}"]="${line##* }"
  done <<<"${current}"
  while read -r line; do
    [ -n "${line}" ] || continue
    unit="${line% *}"
    was="${line##* }"
    backup_durable "${unit}" || continue
    base=$((base + was))
    now=$((now + ${have["${unit}"]:-0}))
    if [ -z "${have["${unit}"]:-}" ]; then
      absent=$((absent + 1))
      [ -n "${first}" ] || first="${unit}"
      if [ "${shown}" -lt "${BACKUP_EVIDENCE_LIMIT}" ]; then
        BACKUP_INTERNAL_EVIDENCE+=("missing [${unit}] was [${was}] against [${baseline}]")
        shown=$((shown + 1))
      fi
    fi
  done <<<"$(backup_manifest_fingerprint "${baseline}")"
  percent=0
  [ "${base}" -gt 0 ] && percent=$(((base - now) * 100 / base))
  if [ "${absent}" -gt 0 ] || { [ "${BACKUP_SHRINK_PERCENT}" -gt 0 ] && [ "${percent}" -gt "${BACKUP_SHRINK_PERCENT}" ]; }; then
    BACKUP_INTERNAL_VERDICT="${BACKUP_STATE_REGRESSED}"
    BACKUP_INTERNAL_EVIDENCE+=("regressed [${absent}] closed units missing against [${baseline}], total [-${percent}]% beyond [${BACKUP_SHRINK_PERCENT}]%${first:+, first [${first}]}")
  fi
}

backup_manifested() {
  local run="${BACKUP_RUN_TIMESTAMP}" meta kind parent baseline current count line evidence
  meta="${BACKUP_INTERNAL_ROOT_DIR}/${run}/.meta"
  mkdir -p "${meta}" || return 1
  kind="full"
  backup_is_delta "$(basename "${BACKUP_TARGET_PATH}")" && kind="delta"
  parent=""
  [ "${kind}" = "delta" ] && parent="$(backup_previous "${run}")"
  current="$(backup_fingerprinted "${BACKUP_TARGET_PATH}")" || current=""
  baseline="$(backup_baseline "${run}")"
  backup_regression "${current}" "${baseline}"
  {
    echo "{"
    echo "  \"kind\": \"${kind}\","
    echo "  \"parent\": \"${parent}\","
    echo "  \"source_version\": \"$(backup_json_text "${BACKUP_SOURCE_VERSION}")\","
    echo "  \"verdict\": \"${BACKUP_INTERNAL_VERDICT}\","
    echo "  \"accepted\": false,"
    echo "  \"baseline\": \"${baseline}\","
    echo "  \"evidence\": ["
    evidence=0
    for line in "${BACKUP_INTERNAL_EVIDENCE[@]}"; do
      [ "${evidence}" -gt 0 ] && echo ","
      printf '    "%s"' "$(backup_json_text "${line}")"
      evidence=$((evidence + 1))
    done
    [ "${evidence}" -gt 0 ] && echo
    echo "  ],"
    echo "  \"fingerprint\": {"
    count=0
    while read -r line; do
      [ -n "${line}" ] || continue
      [ "${count}" -gt 0 ] && echo ","
      printf '    "%s": %s' "$(backup_json_text "${line% *}")" "${line##* }"
      count=$((count + 1))
    done <<<"${current}"
    [ "${count}" -gt 0 ] && echo
    echo "  }"
    echo "}"
  } >"${meta}/${BACKUP_MANIFEST_LEAF}.tmp" && mv "${meta}/${BACKUP_MANIFEST_LEAF}.tmp" "${meta}/${BACKUP_MANIFEST_LEAF}" || return 1
  for line in "${BACKUP_INTERNAL_EVIDENCE[@]}"; do
    echo "Backup ${line}" >&2
  done
  echo "Manifest [${BACKUP_INTERNAL_VERDICT}] kind [${kind}] parent [${parent:-none}] units [${count}]"
}

backup_accepted() {
  local run="${1:-}" path
  path="$(backup_manifest_path "${run}")"
  [ -f "${path}" ] || {
    echo "No manifest for run [${run}] under [${BACKUP_INTERNAL_ROOT_DIR}]" >&2
    return 1
  }
  sed "s/^  \"verdict\": \".*\",\$/  \"verdict\": \"${BACKUP_STATE_SUCCESS}\",/; s/^  \"accepted\": false,\$/  \"accepted\": true,/" "${path}" >"${path}.tmp" && mv "${path}.tmp" "${path}" || return 1
  echo "Accepted run [${run}]"
}

backup_anchor() {
  local names index run newest
  mapfile -t names < <(backup_listed)
  [ "${#names[@]}" -gt 0 ] || return 0
  newest="${names[-1]}"
  [ "$(backup_manifest_field "${newest}" verdict)" = "${BACKUP_STATE_REGRESSED}" ] || return 0
  for ((index = ${#names[@]} - 2; index >= 0; index--)); do
    run="${names[index]}"
    [ "$(backup_manifest_field "${run}" verdict)" = "${BACKUP_STATE_SUCCESS}" ] || continue
    printf '%s\n' "${run}"
    return 0
  done
}

backup_closure() {
  local dir="${1}" index run parent
  local -n closure_keep="${2}"
  local names=()
  mapfile -t names < <(backup_listed "${dir}")
  for ((index = ${#names[@]} - 1; index >= 0; index--)); do
    run="${names[index]}"
    [ -n "${closure_keep["${run}"]:-}" ] || continue
    backup_dir_is_full "${dir}" "${run}" && continue
    parent="$(BACKUP_INTERNAL_ROOT_DIR="${dir}" backup_manifest_field "${run}" parent)"
    if [ -n "${parent}" ] && [ -d "${dir}/${parent}" ]; then
      closure_keep["${parent}"]="${closure_keep["${parent}"]:-parent}"
    fi
  done
}

backup_kept_next() {
  local dir="${1}" policy="${2}" names=() run anchor cutoff index
  declare -A kept=()
  mapfile -t names < <(backup_listed "${dir}")
  [ "${#names[@]}" -gt 0 ] || return 0
  case "${policy}" in
  gfs)
    while read -r run; do
      [ -n "${run}" ] && kept["${run}"]=gfs
    done < <(backup_gfs_kept "${dir}" "${BACKUP_NEXT_KEEP_DAILY:-${ZIGBEE2MQTT_BACKUP_NEXT_KEEP_DAILY:-${BACKUP_KEEP_DAILY}}}" "${BACKUP_NEXT_KEEP_WEEKLY:-${ZIGBEE2MQTT_BACKUP_NEXT_KEEP_WEEKLY:-${BACKUP_KEEP_WEEKLY}}}" "${BACKUP_NEXT_KEEP_MONTHLY:-${ZIGBEE2MQTT_BACKUP_NEXT_KEEP_MONTHLY:-${BACKUP_KEEP_MONTHLY}}}")
    ;;
  *)
    cutoff=$(($(date +%s) - ${BACKUP_NEXT_RETAIN_DAYS:-${ZIGBEE2MQTT_BACKUP_NEXT_RETAIN_DAYS:-${BACKUP_RETAIN_DAYS}}} * 86400))
    for run in "${names[@]}"; do
      [ "$(backup_epoch "${run}")" -ge "${cutoff}" ] && kept["${run}"]=window
    done
    ;;
  esac
  kept["${names[-1]}"]="${kept["${names[-1]}"]:-newest}"
  anchor="$(backup_anchor)"
  if [ -n "${anchor}" ]; then
    kept["${anchor}"]="${kept["${anchor}"]:-anchor}"
    for ((index = ${#names[@]} - 1; index >= 0; index--)); do
      [ "${names[index]}" \> "${anchor}" ] && continue
      kept["${names[index]}"]="${kept["${names[index]}"]:-anchor}"
      backup_dir_is_full "${dir}" "${names[index]}" && break
    done
  fi
  backup_closure "${dir}" kept
  for run in "${!kept[@]}"; do
    printf '%s\n' "${run}"
  done | sort
}

backup_removed() {
  local dir="${1}" run="${2}" reason="${3}" policy="${4:-window}"
  if [ -z "${BACKUP_INTERNAL_NEXT_FOR:-}" ] || [ "${BACKUP_INTERNAL_NEXT_FOR}" != "${dir}|${policy}" ]; then
    BACKUP_INTERNAL_NEXT_FOR="${dir}|${policy}"
    BACKUP_INTERNAL_NEXT_KEPT="$(backup_kept_next "${dir}" "${policy}")"
  fi
  if grep -Fxq -- "${run}" <<<"${BACKUP_INTERNAL_NEXT_KEPT}"; then
    echo "Prune disagreement run [${run}] old [delete] new [keep] reason [${reason}]"
    return 0
  fi
  rm -rf "${dir:?}/${run}"
  echo "Pruned backup [${run}] ${reason}"
}

# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, checks the archive's integrity, renames the temporary file on success, prunes and
# sets the exit code. Define backup_written below, naming the backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". A snippet copying files passes
# backup_files a root under BACKUP_SOURCE_PATH and the names of its include and exclude arrays, an
# absent include fails the backup and whatever under the root neither array covers is reported. A
# snippet leaving the estate changed while it works, such as one stopping its own container, also
# defines backup_interrupted, called on INT, TERM or HUP but never on a backup that merely fails, and
# backup_completed, called once the archive has been named and kept whatever the outcome, whose
# non-zero return fails the run without discarding the archive. Never assign another wrapper
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
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
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

case "${1:-}" in
--accept=*)
  backup_accepted "${1#--accept=}"
  exit $?
  ;;
esac

if [ "${1:-}" = "--prune" ]; then
  backup_pruned "${2}"
  exit 0
fi

if [ "${1:-}" = "--prune-gfs" ]; then
  backup_pruned_gfs "${2}"
  exit 0
fi

asystem_locked "${BACKUP_MODULE_NAME}" "$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")" "${BACKUP_LOCK_WAIT:-300}" || exit 1

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
if backup_written; then
  if [ -z "${BACKUP_TARGET_PATH}" ]; then
    echo "Nothing named the backup, call backup_target in backup_written" >&2
  elif [ ! -s "${BACKUP_TARGET_PATH}.tmp" ]; then
    echo "Backup [${BACKUP_TARGET_PATH}] was written empty, discarding it" >&2
  else
    case "${BACKUP_TARGET_PATH}" in
    *.gz) BACKUP_INTERNAL_VERIFIER="gzip" ;;
    *.zip) BACKUP_INTERNAL_VERIFIER="unzip" ;;
    esac
    if [ -n "${BACKUP_INTERNAL_VERIFIER}" ] && ! command -v "${BACKUP_INTERNAL_VERIFIER}" >/dev/null 2>&1; then
      echo "Backup [${BACKUP_TARGET_PATH}] cannot be checked, [${BACKUP_INTERNAL_VERIFIER}] is not installed, discarding it" >&2
    elif [ -n "${BACKUP_INTERNAL_VERIFIER}" ] && ! "${BACKUP_INTERNAL_VERIFIER}" -t "${BACKUP_TARGET_PATH}.tmp" >/dev/null 2>&1; then
      echo "Backup [${BACKUP_TARGET_PATH}] failed its integrity check, discarding it" >&2
    else
      BACKUP_INTERNAL_WRITTEN="true"
    fi
  fi
fi
if [ "${BACKUP_INTERNAL_WRITTEN}" = "true" ]; then
  mv "${BACKUP_TARGET_PATH}.tmp" "${BACKUP_TARGET_PATH}"
  BACKUP_INTERNAL_SIZE="$(du -m "${BACKUP_TARGET_PATH}" | cut -f1)"
  echo "Finished backup [${BACKUP_INTERNAL_SIZE}] MB in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds to [${BACKUP_TARGET_PATH}]"
  backup_manifested || echo "Manifest for [${BACKUP_RUN_TIMESTAMP}] could not be written" >&2
  [ "${BACKUP_PRUNE:-true}" = "true" ] && backup_pruned
  rm -rf "$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/replaced"
else
  echo "Failed backup in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds" >&2
  BACKUP_INTERNAL_STATUS=1
fi
backup_completed || BACKUP_INTERNAL_STATUS=1

find "${BACKUP_INTERNAL_ROOT_DIR}" -depth -type d -empty -delete 2>/dev/null
exit "${BACKUP_INTERNAL_STATUS}"