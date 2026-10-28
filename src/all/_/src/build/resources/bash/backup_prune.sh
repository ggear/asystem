# shellcheck shell=bash
# shellcheck disable=SC2034

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
