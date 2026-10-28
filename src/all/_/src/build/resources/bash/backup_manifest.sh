# shellcheck shell=bash
# shellcheck disable=SC2034

BACKUP_MANIFEST_LEAF="manifest.json"

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
