# shellcheck shell=bash

stage_start() {
  local share index service failed=0
  index="$(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .index // empty' "${BACKUP_CONFIG}" 2>/dev/null)"
  if [ -n "${index}" ]; then
    share="/share/${index}0"
  else
    share="$(awk '$1 !~ /^#/ && $2 ~ /^\/share\/[0-9]+$/ { print $2 }' /etc/fstab | sort |
      while read -r mount; do mountpoint -q "${mount}" && { echo "${mount}"; break; }; done)"
  fi
  [ -n "${share}" ] || { echo "[secondary] no share destination resolved" >&2; return 1; }
  backup_mount "${share}" || return 1
  mkdir -p "${share}/backup"
  local promote="supervisor" status
  for status in "${BACKUP_RUN_PATH}"/stage/primary/service/*/status.json; do
    [ -f "${status}" ] || continue
    [ "$(jq -r '.success_bool // false' "${status}" 2>/dev/null)" = "true" ] &&
      promote="${promote} $(basename "$(dirname "${status}")")"
  done
  for service in ${promote}; do
    local source="${BACKUP_HOME_ROOT}/${service}/backup/"
    local target="${share}/backup/${service}"
    [ -d "${source}" ] || continue
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -delete 2>/dev/null
    echo "[secondary] promoting [${service}] to [${target}]"
    local output
    output="$(rsync -a --stats --temp-dir="${target}/.rsync" -- "${source}" "${target}/" 2>&1)" || failed=1
    printf '%s\n' "${output}"
    backup_count "${output}"
    local prune="${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh"
    if [ -x "${prune}" ]; then
      bash "${prune}" --prune-gfs "${target}" || true
    else
      backup_thin "${target}"
    fi
  done
  backup_usage "${share}"
  return "${failed}"
}

stage_stop() {
  pkill -TERM -f "rsync .*${BACKUP_HOME_ROOT}" 2>/dev/null || true
}
