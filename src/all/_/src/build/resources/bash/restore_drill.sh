# shellcheck shell=bash
# shellcheck disable=SC2034

RESTORE_SCRATCH=""

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
  local want have shorts scratch before after file extracts="false" addressed="false"
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
    extracts="false"
    for file in "${RESTORE_CHAIN_FILES[@]}"; do
      case "${file}" in *.tar.gz | *.zip) extracts="true" ;; esac
    done
    if [ "${extracts}" = "true" ]; then
      before="$(restore_fingerprinted "${scratch}" | sort)"
    else
      before="${want}"
    fi
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
    if [ "${extracts}" = "true" ]; then
      after="$(restore_fingerprinted "${scratch}" | sort)"
    else
      after="${before}"
    fi
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
