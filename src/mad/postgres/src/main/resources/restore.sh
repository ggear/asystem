#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

#   restore.sh [--mode=replace|merge|drill] [--from=<timestamp>] [--file=<path>] [--source=<dir>]
#              [--record=<stage>] [--keep-scratch] [--force] [--no-backup]
#
#   bare      read only, resolves the chain and prints the plan, changes nothing
#   --force   applies the plan, the only destructive form
#
#   mode      replace restores wholesale, drill proves the backup restores without touching live,
#             merge puts back history live lost, offered only to a module defining restore_merged
#   from      the run to restore, a backup timestamp, defaulting to the newest run not regressed
#   file      an artifact path outright, for one lifted off the share or elsewhere
#   source    a directory of runs searched alone, for a chain pinned outside the stages
#   record    the stage under whose .meta a drill writes its verdict, primary or secondary
#   keep-scratch  leave the scratch directory behind for inspection
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
RESTORE_MODE="replace"
RESTORE_SOURCE_DIR=""
RESTORE_KEEP_SCRATCH="false"
RESTORE_RECORD=""
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
  --mode=*) RESTORE_MODE="${1#--mode=}" ;;
  --source=*) RESTORE_SOURCE_DIR="${1#--source=}" ;;
  --record=*) RESTORE_RECORD="${1#--record=}" ;;
  --keep-scratch) RESTORE_KEEP_SCRATCH="true" ;;
  --file=*) RESTORE_FILE="${1#--file=}" ;;
  --file)
    shift
    RESTORE_FILE="${1:-}"
    ;;
  *)
    echo "Usage: ${0} [--mode=replace|merge|drill] [--from=<timestamp>] [--file=<path>] [--source=<dir>] [--record=<stage>] [--keep-scratch] [--force] [--no-backup]" >&2
    exit 2
    ;;
  esac
  shift
done

RESTORE_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${RESTORE_INTERNAL_ENV}" ] && . "${RESTORE_INTERNAL_ENV}"

RESTORE_MODULE_NAME="postgres"
RESTORE_SOURCE_PATH="${RESTORE_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/postgres/latest}}"
RESTORE_INTERNAL_SOURCE_DIR="$(readlink -f "${RESTORE_SOURCE_PATH}")"
RESTORE_INTERNAL_ROOT_DIR="$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")/backup"
RESTORE_INTERNAL_BACKUP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup.sh"
RESTORE_FULL_SUFFIX="_full"
RESTORE_DELTA_SUFFIX="_delta"
RESTORE_SERVICE_STATE="stopped"
RESTORE_SOURCE_FILE=""
RESTORE_SOURCE_VERSION=""
RESTORE_RUN_TIMESTAMP=""
RESTORE_CARRY=()
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
      case "${name}" in *"${RESTORE_FULL_SUFFIX}".* | *"${RESTORE_DELTA_SUFFIX}".*) ;; *) continue ;; esac
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
  local declared="${1:-}" target="${2:-${RESTORE_SOURCE_PATH}}" replaced path entry relative
  [ -d "${target}" ] || { restore_fault "no restore target [${target}]"; return 1; }
  replaced="$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")/replaced/${RESTORE_RUN_TIMESTAMP}"
  if [ -n "${declared}" ]; then
    IFS=: read -r -a RESTORE_INTERNAL_PATHS <<<"${declared}"
    for path in "${RESTORE_INTERNAL_PATHS[@]}"; do
      [ -e "${target}/${path}" ] || [ -L "${target}/${path}" ] || continue
      mkdir -p "${replaced}/$(dirname "${path}")"
      mv "${target}/${path}" "${replaced}/${path}" || { restore_fault "could not move [${target}/${path}] aside to [${replaced}]"; return 1; }
    done
    [ -d "${replaced}" ] && restore_changed "moved [${declared}] aside to [${replaced}]"
  fi
  tar --extract --directory "${target}" --numeric-owner --preserve-permissions \
    --file - <"${RESTORE_SOURCE_FILE}" 2>/dev/null ||
    tar --extract --gzip --directory "${target}" --numeric-owner --preserve-permissions \
      --file "${RESTORE_SOURCE_FILE}" || {
    restore_fault "could not extract [${RESTORE_SOURCE_FILE}] into [${target}]"
    return 1
  }
  restore_changed "extracted [${declared:-archive}] into [${target}]"
  if [ -d "${replaced}" ] && [ "${#RESTORE_CARRY[@]}" -gt 0 ]; then
    for path in "${RESTORE_CARRY[@]}"; do
      while IFS= read -r -d '' entry; do
        relative="${entry#"${replaced}/"}"
        case "${relative}" in *-wal | *-shm | *-journal) continue ;; esac
        [ -e "${target}/${relative}" ] && continue
        mkdir -p "${target}/$(dirname "${relative}")"
        mv "${entry}" "${target}/${relative}" && restore_changed "carried [${relative}] back from [${replaced}]"
      done < <(find "${replaced}" -name "${path}" -print0)
    done
  fi
}

restore_backed() {
  [ "${RESTORE_BACKUP}" = "true" ] || { restore_report "skipping the safety backup, [--no-backup] given"; return 0; }
  [ -f "${RESTORE_INTERNAL_BACKUP}" ] || { restore_report "skipping the safety backup, no [backup.sh] beside this script"; return 0; }
  restore_report "taking a safety backup of the current data first ..."
  BACKUP_PRUNE=false BACKUP_SKIP_HOURS=0 BACKUP_SERVICE_RESTART=false bash "${RESTORE_INTERNAL_BACKUP}" || {
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
BACKUP_STATE_REGRESSED="regressed"
BACKUP_STATE_SUCCESS="success"
RESTORE_LIVE_ADDRESS=""
RESTORE_CHAIN_RUNS=()
RESTORE_CHAIN_FILES=()
RESTORE_SCRATCH=""
RESTORE_PLANNED=()

restore_roots() {
  local root
  if [ -n "${RESTORE_SOURCE_DIR}" ]; then
    printf '%s\n' "${RESTORE_SOURCE_DIR}"
    return 0
  fi
  printf '%s\n' "${RESTORE_INTERNAL_ROOT_DIR}"
  for root in /share/*/backup/"${RESTORE_MODULE_NAME}"; do
    [ -d "${root}" ] && printf '%s\n' "${root}"
  done
}

restore_run_dir() {
  local root
  while read -r root; do
    [ -d "${root}/${1}" ] && {
      printf '%s\n' "${root}/${1}"
      return 0
    }
  done < <(restore_roots)
  return 1
}

restore_runs_all() {
  local root
  while read -r root; do
    [ -d "${root}" ] || continue
    find "${root}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
      grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$'
  done < <(restore_roots) | sort -u
}

restore_artifact_of() {
  local dir="${1}" path
  for path in "${dir}"/*; do
    [ -f "${path}" ] || continue
    case "${path}" in *"${RESTORE_FULL_SUFFIX}".* | *"${RESTORE_DELTA_SUFFIX}".*)
      printf '%s\n' "${path}"
      return 0
      ;;
    esac
  done
  return 1
}

restore_manifest_of() {
  local dir
  dir="$(restore_run_dir "${1}")" || return 0
  printf '%s\n' "${dir}/.meta/manifest.json"
}

restore_manifest_field() {
  local path
  path="$(restore_manifest_of "${1}")"
  [ -f "${path}" ] || return 0
  sed -n 's/^  "'"${2}"'": "\{0,1\}\([^",]*\)"\{0,1\},\{0,1\}$/\1/p' "${path}" | head -n 1
}

restore_manifest_units() {
  local path
  path="$(restore_manifest_of "${1}")"
  [ -f "${path}" ] || return 0
  awk '/^  "fingerprint": \{$/ { inside = 1; next } inside && /^  \}/ { exit } inside { print }' "${path}" |
    sed 's/^    "\(.*\)": \([0-9]*\),\{0,1\}$/\1 \2/' | sort
}

restore_default_run() {
  local run
  while read -r run; do
    [ "$(restore_manifest_field "${run}" verdict)" = "${BACKUP_STATE_REGRESSED}" ] && continue
    restore_artifact_of "$(restore_run_dir "${run}")" >/dev/null || continue
    printf '%s\n' "${run}"
  done < <(restore_runs_all | sort -r) | head -n 1
}

restore_previous_run() {
  local run="${1}" candidate previous=""
  while read -r candidate; do
    [ "${candidate}" \< "${run}" ] || continue
    restore_artifact_of "$(restore_run_dir "${candidate}")" >/dev/null 2>&1 && previous="${candidate}"
  done < <(restore_runs_all)
  printf '%s\n' "${previous}"
}

restore_chain_resolved() {
  local run="${1}" dir file parent declared
  local -a runs=() files=()
  RESTORE_CHAIN_RUNS=()
  RESTORE_CHAIN_FILES=()
  while true; do
    dir="$(restore_run_dir "${run}")" || {
      restore_fault "no backup run [${run}] under [$(restore_roots | tr '\n' ' ')]"
      return 1
    }
    file="$(restore_artifact_of "${dir}")" || {
      restore_fault "no artifact in run [${run}]"
      return 1
    }
    runs+=("${run}")
    files+=("${file}")
    case "${file}" in *"${RESTORE_DELTA_SUFFIX}".*) ;; *) break ;; esac
    parent="$(restore_previous_run "${run}")"
    declared="$(restore_manifest_field "${run}" parent)"
    if [ -n "${declared}" ] && [ "${declared}" != "${parent}" ]; then
      restore_report "manifest parent [${declared}] of [${run}] differs from the preceding run [${parent}], using the preceding run"
    fi
    [ -n "${parent}" ] || {
      restore_fault "delta run [${run}] has no run before it to hang off, so its chain has no full"
      return 1
    }
    run="${parent}"
  done
  local index
  for ((index = ${#runs[@]} - 1; index >= 0; index--)); do
    RESTORE_CHAIN_RUNS+=("${runs[index]}")
    RESTORE_CHAIN_FILES+=("${files[index]}")
  done
}

restore_intact_file() {
  case "${1}" in
  *.gz) gzip -t "${1}" 2>/dev/null ;;
  *.zip) unzip -t "${1}" >/dev/null 2>&1 ;;
  *) return 0 ;;
  esac
}

restore_chain_intact() {
  local file bad=0
  for file in "${RESTORE_CHAIN_FILES[@]}"; do
    restore_intact_file "${file}" || {
      restore_fault "the artifact failed its integrity check [${file}]"
      bad=1
    }
  done
  return "${bad}"
}

restore_compared() {
  local want="${1}" have="${2}" unit count now short=0 line
  declare -A held=()
  while read -r line; do
    [ -n "${line}" ] && held["${line% *}"]="${line##* }"
  done <<<"${have}"
  while read -r line; do
    [ -n "${line}" ] || continue
    unit="${line% *}"
    count="${line##* }"
    now="${held["${unit}"]:-}"
    if [ -z "${now}" ] || [ "${now}" -lt "${count}" ]; then
      echo "short [${unit}] wants [${count}] holds [${now:-0}]"
      short=$((short + 1))
    fi
  done <<<"${want}"
  return "$((short > 0))"
}

restore_scratch_dir() {
  printf '%s\n' "$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")/restore/${RESTORE_RUN_TIMESTAMP}"
}

restore_staged() {
  local file scratch
  scratch="$(restore_scratch_dir)"
  rm -rf "${scratch}"
  mkdir -p "${scratch}" || return 1
  for file in "${RESTORE_CHAIN_FILES[@]}"; do
    case "${file}" in
    *.tar.gz) tar --extract --gzip --directory "${scratch}" --file "${file}" 2>/dev/null || return 1 ;;
    *.zip) unzip -q "${file}" -d "${scratch}" || return 1 ;;
    *) ;;
    esac
  done
  printf '%s\n' "${scratch}"
}

restore_sealed() {
  chmod -R a-w "${1}" 2>/dev/null || true
}

restore_teardown() {
  [ -n "${1:-}" ] && [ -d "${1}" ] || return 0
  chmod -R u+w "${1}" 2>/dev/null || true
  rm -rf "${1:?}"
}

restore_fingerprint_scratch() {
  local scratch="${1}" want="${2}" line unit size
  while read -r line; do
    [ -n "${line}" ] || continue
    unit="${line% *}"
    if [ -e "${scratch}/${unit}" ]; then
      size="$(find "${scratch}/${unit}" -type f -printf '%s\n' 2>/dev/null | awk '{ total += $1 } END { print total + 0 }')"
      echo "${unit} ${size}"
    fi
  done <<<"${want}"
}

restore_fingerprinted() {
  local target="${1:-}" includes
  case "${target}" in
  *.sql.gz | *.zip | *.tar.gz)
    includes=()
    while read -r line; do
      [ -n "${line}" ] && includes+=("${line% *}")
    done <<<"$(restore_manifest_units "${RESTORE_RUN_TIMESTAMP}")"
    BACKUP_FINGERPRINT_INCLUDES=("${includes[@]}")
    backup_fingerprinted_default "${target}"
    ;;
  *)
    if [ -d "${target}" ]; then
      restore_fingerprint_scratch "${target}" "$(restore_manifest_units "${RESTORE_RUN_TIMESTAMP}")"
    fi
    ;;
  esac
}

restore_recorded() {
  local verdict="${1}" detail="${2}" dir meta
  [ -n "${RESTORE_RECORD}" ] || return 0
  dir="$(restore_run_dir "${RESTORE_RUN_TIMESTAMP}")" || return 0
  meta="${dir}/.meta/${RESTORE_RECORD}"
  mkdir -p "${meta}" 2>/dev/null || return 0
  printf '{\n  "verdict": "%s",\n  "run": "%s",\n  "detail": "%s"\n}\n' "${verdict}" "${RESTORE_RUN_TIMESTAMP}" "${detail}" >"${meta}/drill.json"
}

restore_drilled() {
  local want have shorts scratch before after file addressed="false"
  declare -F backup_fingerprinted >/dev/null && addressed="true"
  want="$(restore_manifest_units "${RESTORE_RUN_TIMESTAMP}")"
  restore_report "drill     chain of [${#RESTORE_CHAIN_FILES[@]}] artifact(s), manifest holds [$(grep -c . <<<"${want}")] unit(s)"
  if [ -z "${want}" ]; then
    restore_report "the run has no manifest fingerprint, so only integrity and staging are proven"
  fi
  scratch="$(restore_staged)" || {
    restore_fault "could not stage [${RESTORE_RUN_TIMESTAMP}] into scratch"
    restore_teardown "${scratch:-}"
    restore_recorded failure "staging failed"
    return 1
  }
  RESTORE_SCRATCH="${scratch}"
  if [ "${addressed}" = "false" ]; then
    for file in "${RESTORE_CHAIN_FILES[@]}"; do
      have="$(restore_fingerprinted "${file}")"
    done
    shorts="$(restore_compared "${want}" "${have}")" || {
      restore_fault "the artifact holds less than its manifest says"
      printf '%s\n' "${shorts}" | while read -r line; do restore_report "${line}"; done
      restore_teardown "${scratch}"
      restore_recorded failure "artifact short"
      return 1
    }
    before="$(restore_fingerprinted "${scratch}" | sort)"
  else
    before="$(backup_fingerprinted "${scratch}" | sort)" || {
      restore_fault "could not fingerprint scratch [${scratch}]"
      restore_teardown "${scratch}"
      restore_recorded failure "fingerprint failed"
      return 1
    }
  fi
  shorts="$(restore_compared "${want}" "${before}")" || {
    restore_fault "scratch holds less than the manifest says"
    printf '%s\n' "${shorts}" | while read -r line; do restore_report "${line}"; done
    [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
    restore_recorded failure "scratch short"
    return 1
  }
  if declare -F restore_checked >/dev/null; then
    restore_checked "${scratch}" || {
      restore_fault "the module check of scratch [${scratch}] failed"
      [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
      restore_recorded failure "module check failed"
      return 1
    }
  fi
  restore_sealed "${scratch}" || {
    restore_fault "could not seal scratch [${scratch}] read only"
    [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
    restore_recorded failure "seal failed"
    return 1
  }
  if [ "${addressed}" = "false" ]; then
    after="$(restore_fingerprinted "${scratch}" | sort)"
  else
    after="$(backup_fingerprinted "${scratch}" | sort)"
  fi
  if [ "${before}" != "${after}" ]; then
    restore_fault "scratch changed after it was sealed"
    [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
    restore_recorded failure "scratch moved after sealing"
    return 1
  fi
  [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
  restore_report "drill passed, every manifest unit is held and scratch is read only"
  restore_recorded success "drilled"
}

restore_planned_units() {
  local staged="${1}" live="${2}" line unit count
  declare -A held=()
  while read -r line; do
    [ -n "${line}" ] && held["${line% *}"]="${line##* }"
  done <<<"${live}"
  while read -r line; do
    [ -n "${line}" ] || continue
    unit="${line% *}"
    count="${line##* }"
    [ "${held["${unit}"]:-}" = "${count}" ] || echo "${unit}"
  done <<<"${staged}"
}

restore_merged_progress() {
  printf '%s\n' "$(dirname "$(restore_scratch_dir)")/${RESTORE_RUN_TIMESTAMP}.merged"
}

restore_merge() {
  local staged live after unit planned progress scratch
  if ! declare -F restore_merged >/dev/null; then
    restore_fault "module [${RESTORE_MODULE_NAME}] defines no restore_merged, merge is not offered"
    return 1
  fi
  scratch="$(restore_staged)" || {
    restore_fault "could not stage [${RESTORE_RUN_TIMESTAMP}] into scratch"
    return 1
  }
  RESTORE_SCRATCH="${scratch}"
  staged="$(backup_fingerprinted "${scratch}")"
  restore_sealed "${scratch}" || {
    restore_fault "could not seal scratch [${scratch}] read only"
    restore_teardown "${scratch}"
    return 1
  }
  live="$(backup_fingerprinted "${RESTORE_LIVE_ADDRESS}")"
  mapfile -t RESTORE_PLANNED < <(restore_planned_units "${staged}" "${live}")
  restore_report "merge     [${#RESTORE_PLANNED[@]}] closed unit(s) differ from live"
  for unit in "${RESTORE_PLANNED[@]:0:20}"; do
    restore_report "plan      [${unit}]"
  done
  [ "${#RESTORE_PLANNED[@]}" -gt 20 ] && restore_report "plan      and [$((${#RESTORE_PLANNED[@]} - 20))] more"
  if [ "${RESTORE_FORCE}" != "true" ]; then
    [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
    return 0
  fi
  restore_backed || return 1
  progress="$(restore_merged_progress)"
  mkdir -p "$(dirname "${progress}")"
  touch "${progress}"
  local jobs="${RESTORE_MERGE_JOBS:-3}" running=0 failures
  failures="${progress}.failed"
  rm -f "${failures}"
  for unit in "${RESTORE_PLANNED[@]}"; do
    grep -Fxq -- "${unit}" "${progress}" && continue
    if [ "${jobs}" -le 1 ]; then
      restore_merged "${unit}" "${scratch}" || {
        restore_fault "could not merge [${unit}]"
        return 1
      }
      echo "${unit}" >>"${progress}"
      RESTORE_CHANGED=$((RESTORE_CHANGED + 1))
      continue
    fi
    (restore_merged "${unit}" "${scratch}" && echo "${unit}" >>"${progress}" || echo "${unit}" >>"${failures}") &
    running=$((running + 1))
    if [ "${running}" -ge "${jobs}" ]; then
      wait -n || true
      running=$((running - 1))
    fi
  done
  wait || true
  if [ -s "${failures}" ]; then
    while read -r unit; do
      restore_fault "could not merge [${unit}]"
    done <"${failures}"
    return 1
  fi
  [ "${jobs}" -gt 1 ] && RESTORE_CHANGED=$((RESTORE_CHANGED + $(grep -c . "${progress}")))
  restore_restarted
  declare -A held=() want=()
  while read -r line; do
    [ -n "${line}" ] && want["${line% *}"]="${line##* }"
  done <<<"${staged}"
  local attempt=0 short=0 shorts=()
  while true; do
    after="$(backup_fingerprinted "${RESTORE_LIVE_ADDRESS}")"
    held=()
    while read -r line; do
      [ -n "${line}" ] && held["${line% *}"]="${line##* }"
    done <<<"${after}"
    shorts=()
    for unit in "${RESTORE_PLANNED[@]}"; do
      [ "${held["${unit}"]:-0}" -ge "${want["${unit}"]:-0}" ] || shorts+=("${unit}")
    done
    [ "${#shorts[@]}" -eq 0 ] && break
    attempt=$((attempt + 1))
    [ "${attempt}" -lt "${RESTORE_VERIFY_ATTEMPTS:-24}" ] || break
    sleep "${RESTORE_VERIFY_SLEEP:-5}"
  done
  for unit in "${shorts[@]}"; do
    restore_fault "unit [${unit}] holds [${held["${unit}"]:-0}] after the merge, wants at least [${want["${unit}"]}]"
    short=$((short + 1))
  done
  [ "${short}" -eq 0 ] && rm -f "${progress}" "${failures}"
  [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
  return "$((short > 0))"
}

restore_restarted() {
  docker restart "${RESTORE_MODULE_NAME}" >/dev/null 2>&1 || true
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
    docker exec --user root "${container}" psql -U "${user}" -d "${database}" -v ON_ERROR_STOP=1 -qc "DROP EXTENSION IF EXISTS timescaledb CASCADE" >/dev/null || return 1
  done
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root "${container}" psql -U "${user}" -d postgres -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS \"${database}\" WITH (FORCE)" >/dev/null || return 1
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

restore_failed() {
  echo && echo "❌ Restore found [${RESTORE_FAULTS}] fault(s), changed [${RESTORE_CHANGED}]" && echo
  exit 1
}

asystem_locked "${RESTORE_MODULE_NAME}" "$(dirname "${RESTORE_INTERNAL_SOURCE_DIR}")" "${RESTORE_LOCK_WAIT:-300}" || exit 1
echo && echo "Restore $([ "${RESTORE_FORCE}" = "true" ] && echo apply || echo plan) [${RESTORE_MODULE_NAME}] mode [${RESTORE_MODE}] against [${RESTORE_SOURCE_PATH}] forced [${RESTORE_FORCE}]" && echo
case "${RESTORE_MODE}" in replace | drill | merge) ;; *)
  restore_fault "unknown mode [${RESTORE_MODE}], taking one of [replace drill merge]"
  restore_failed
  ;;
esac
if [ -n "${RESTORE_FILE}" ]; then
  restore_resolved || restore_failed
  RESTORE_CHAIN_FILES=("${RESTORE_SOURCE_FILE}")
else
  RESTORE_RUN_TIMESTAMP="${RESTORE_FROM:-$(restore_default_run)}"
  [ -n "${RESTORE_RUN_TIMESTAMP}" ] || { restore_fault "no accepted backup run under [$(restore_roots | tr '\n' ' ')]"; restore_failed; }
  if [ "$(restore_manifest_field "${RESTORE_RUN_TIMESTAMP}" verdict)" = "${BACKUP_STATE_REGRESSED}" ]; then
    restore_forced "restore the regressed run [${RESTORE_RUN_TIMESTAMP}], a regressed backup holds less than the one before it" || restore_failed
  fi
  restore_chain_resolved "${RESTORE_RUN_TIMESTAMP}" || restore_failed
  RESTORE_SOURCE_FILE="${RESTORE_CHAIN_FILES[-1]}"
  RESTORE_SOURCE_VERSION="$(restore_versioned "$(basename "${RESTORE_SOURCE_FILE}")")"
  case "${RESTORE_SOURCE_FILE}" in
  *"${RESTORE_DELTA_SUFFIX}".*) RESTORE_INTERNAL_KIND="delta" ;;
  *) RESTORE_INTERNAL_KIND="full" ;;
  esac
fi
restore_report "artifact  [${RESTORE_SOURCE_FILE}]"
restore_report "taken     [${RESTORE_RUN_TIMESTAMP}] from version [${RESTORE_SOURCE_VERSION:-unknown}] kind [${RESTORE_INTERNAL_KIND}] chain [${#RESTORE_CHAIN_FILES[@]}]"
restore_report "size      [$(du -m -s "${RESTORE_SOURCE_FILE}" 2>/dev/null | cut -f1)] MB"
restore_report "service   must be [${RESTORE_SERVICE_STATE}]"
restore_chain_intact || restore_failed
restore_report "integrity passed"
echo
case "${RESTORE_MODE}" in
drill)
  restore_drilled || true
  ;;
merge)
  restore_merge || true
  if [ "${RESTORE_FORCE}" != "true" ] && [ "${RESTORE_FAULTS}" -eq 0 ]; then
    echo && echo "✅ Merge plan resolved, rerun with [--force] to apply, changed [${RESTORE_CHANGED}]" && echo
    exit 0
  fi
  ;;
*)
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
  ;;
esac
echo
if [ "${RESTORE_FAULTS}" -ne 0 ]; then
  echo "❌ Restore found [${RESTORE_FAULTS}] fault(s), changed [${RESTORE_CHANGED}]" && echo
  exit 1
fi
echo "✅ Restore $([ "${RESTORE_MODE}" = "drill" ] && echo drilled || echo applied) from [${RESTORE_RUN_TIMESTAMP}], changed [${RESTORE_CHANGED}]" && echo