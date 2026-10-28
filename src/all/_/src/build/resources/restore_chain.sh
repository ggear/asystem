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
