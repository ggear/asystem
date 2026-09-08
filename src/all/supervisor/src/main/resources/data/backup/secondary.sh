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
  [ -n "${share}" ] || { backup_log ERROR "no share destination resolved for host [${BACKUP_HOST}]"; return 1; }
  backup_log INFO "resolved share [${share}] from [${index:-fstab}]"
  backup_mount "${share}" || return 1
  mkdir -p "${share}/backup"
  local promote="supervisor" status
  for status in "${BACKUP_RUN_PATH}"/stage/primary/service/*/status.json; do
    [ -f "${status}" ] || continue
    [ "$(jq -r '.success_bool // false' "${status}" 2>/dev/null)" = "true" ] &&
      promote="${promote} $(basename "$(dirname "${status}")")"
  done
  local total=0 index_promoted=0
  for service in ${promote}; do total=$(( total + 1 )); done
  backup_log INFO "promoting [${total}] services to [${share}/backup]"
  for service in ${promote}; do
    index_promoted=$(( index_promoted + 1 ))
    local source="${BACKUP_HOME_ROOT}/${service}/backup/"
    local target="${share}/backup/${service}"
    if [ ! -d "${source}" ]; then
      backup_log WARN "skipped [${service}] [${index_promoted}/${total}], no backup directory at [${source}]"
      continue
    fi
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -delete 2>/dev/null
    backup_log INFO "promoting [${service}] [${index_promoted}/${total}] from [${source}] to [${target}]"
    local started; started="$(date +%s)"
    backup_rsync -a --stats --human-readable --out-format='%t %o %f %l' \
      --temp-dir="${target}/.rsync" -- "${source}" "${target}/" || failed=1
    backup_count "${BACKUP_RSYNC_OUTPUT}"
    backup_log INFO "promoted [${service}] in [$(backup_elapsed $(( $(date +%s) - started )))], running total [${BACKUP_FILES}] files, [${BACKUP_SIZE}] MB"
    local prune="${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh"
    if [ -x "${prune}" ]; then
      backup_log INFO "thinning [${target}] with the module pruner [${prune}]"
      bash "${prune}" --prune-gfs "${target}" || true
    else
      backup_log INFO "thinning [${target}] with backup_thin, the module ships no pruner"
      backup_thin "${target}"
    fi
  done
  backup_usage "${share}"
  return "${failed}"
}

stage_stop() {
  backup_log INFO "terminating any running promotion rsync"
  pkill -TERM -f "rsync .*${BACKUP_HOME_ROOT}" 2>/dev/null || true
}
