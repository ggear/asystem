# shellcheck shell=bash
# shellcheck disable=SC2034

# Mirrors metric.BackupState<Name> in supervisor internal/metric/metric_schema.go, which owns the words, as BACKUP_STATE_<NAME>. A supervisor test holds the two equal.
BACKUP_STATE_SUCCESS="success"
BACKUP_STATE_REGRESSED="regressed"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${PREFIX_TOKEN_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_FINGERPRINT_INCLUDES=()
BACKUP_EVIDENCE_LIMIT=20
BACKUP_MANIFEST_LEAF="manifest.json"

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
  [ "${kind}" = "delta" ] && parent="$(backup_parent "${run}")"
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
    done < <(backup_gfs_kept "${dir}" "${BACKUP_NEXT_KEEP_DAILY:-${PREFIX_TOKEN_BACKUP_NEXT_KEEP_DAILY:-${BACKUP_KEEP_DAILY}}}" "${BACKUP_NEXT_KEEP_WEEKLY:-${PREFIX_TOKEN_BACKUP_NEXT_KEEP_WEEKLY:-${BACKUP_KEEP_WEEKLY}}}" "${BACKUP_NEXT_KEEP_MONTHLY:-${PREFIX_TOKEN_BACKUP_NEXT_KEEP_MONTHLY:-${BACKUP_KEEP_MONTHLY}}}")
    ;;
  *)
    cutoff=$(($(date +%s) - ${BACKUP_NEXT_RETAIN_DAYS:-${PREFIX_TOKEN_BACKUP_NEXT_RETAIN_DAYS:-${BACKUP_RETAIN_DAYS}}} * 86400))
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
