# shellcheck shell=bash
# shellcheck disable=SC2034

# Mirrors metric.BackupState<Name> in supervisor internal/metric/metric_schema.go, which owns the words, as BACKUP_STATE_<NAME>. A supervisor test holds the two equal.
BACKUP_STATE_REGRESSED="regressed"
BACKUP_STATE_SUCCESS="success"
RESTORE_CHAIN_RUNS=()
RESTORE_CHAIN_FILES=()

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
    if [ "${RESTORE_VERBOSE:-false}" = "true" ] && [ -n "${declared}" ] && [ "${declared}" != "${parent}" ]; then
      restore_report "chain manifest parent [${declared}] of [${run}] differs from the preceding run [${parent}], using the preceding run"
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
