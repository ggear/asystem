# shellcheck shell=bash
# shellcheck disable=SC2034

# Mirrors metric.BackupState<Name> in supervisor internal/metric/metric_schema.go, which owns the words, as BACKUP_STATE_<NAME>. A supervisor test holds the two equal.
BACKUP_STATE_SUCCESS="success"
BACKUP_STATE_REGRESSED="regressed"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${PREFIX_TOKEN_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_EVIDENCE_LIMIT=20

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
