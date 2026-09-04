# shellcheck shell=bash disable=SC2153

# Shared by every backup stage, sourced by backup.sh before the stage file, never run directly.
#
# The runner owns the run - identity, roots, retention window and timeout are exported as BACKUP_*
# and a stage only reads them. A stage provides stage_start and stage_stop, and reports its work by
# adding to BACKUP_USAGE and the BACKUP_FILES/SIZE counters, directly or through backup_count.

backup_config() {
  local value
  value="$(jq -r "${1} // empty" "${BACKUP_CONFIG}" 2>/dev/null)"
  printf '%s' "${value:-$2}"
}

backup_publish() {
  local topic="$1" payload="$2"
  command -v mosquitto_pub >/dev/null 2>&1 || return 0
  [ -n "${BROKER_HOST:-}" ] || return 0
  mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT:-1883}" \
    ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -q 1 -r -t "${topic}" -m "${payload}" 2>/dev/null || true
}

backup_mount() {
  local target="$1"
  mountpoint -q "${target}" && return 0
  grep -qsE "^[^#][^[:space:]]*[[:space:]]+${target}[[:space:]]" /etc/fstab || {
    echo "[${BACKUP_STAGE}] [${target}] is not mounted and not in /etc/fstab" >&2
    return 1
  }
  echo "[${BACKUP_STAGE}] mounting [${target}]"
  mount "${target}" >/dev/null 2>&1 || ls "${target}" >/dev/null 2>&1 || true
  mountpoint -q "${target}"
}

backup_usage() {
  local uuid file allocation used=0 total=0 percent
  uuid="$(btrfs filesystem show "$1" 2>/dev/null | sed -n 's/.*uuid: //p' | head -1)"
  if [ -n "${uuid}" ]; then
    for file in /sys/fs/btrfs/"${uuid}"/devices/*/size; do
      [ -f "${file}" ] && total=$(( total + $(cat "${file}") * 512 ))
    done
    for allocation in data metadata system; do
      used=$(( used + $(cat "/sys/fs/btrfs/${uuid}/allocation/${allocation}/bytes_used" 2>/dev/null || echo 0) ))
    done
    if [ "${total}" -gt 0 ]; then
      BACKUP_USAGE=$(( used * 100 / total ))
      return 0
    fi
  fi
  percent="$(df --output=pcent "$1" 2>/dev/null | tail -1 | tr -dc '0-9')"
  BACKUP_USAGE="${percent:-0}"
}

backup_field() {
  local value
  value="$(printf '%s\n' "$1" | sed -n "s/^$2//p" | head -1 | cut -d' ' -f1 | tr -dc '0-9')"
  printf '%s' "${value:-0}"
}

backup_count() {
  local output="$1"
  BACKUP_FILES=$(( BACKUP_FILES + $(backup_field "${output}" 'Number of regular files transferred: ') ))
  BACKUP_FILES_HELD=$(( BACKUP_FILES_HELD + $(backup_field "${output}" 'Number of files: ') ))
  BACKUP_FILES_CREATED=$(( BACKUP_FILES_CREATED + $(backup_field "${output}" 'Number of created files: ') ))
  BACKUP_FILES_DELETED=$(( BACKUP_FILES_DELETED + $(backup_field "${output}" 'Number of deleted files: ') ))
  BACKUP_SIZE=$(( BACKUP_SIZE + $(backup_field "${output}" 'Total transferred file size: ') / 1048576 ))
  BACKUP_SIZE_HELD=$(( BACKUP_SIZE_HELD + $(backup_field "${output}" 'Total file size: ') / 1048576 ))
  BACKUP_SENT=$(( BACKUP_SENT + $(backup_field "${output}" 'Total bytes sent: ') / 1048576 ))
}

backup_thin() {
  local dir="$1" names name stamp bucket count index
  mapfile -t names < <(find "${dir}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort)
  [ "${#names[@]}" -gt 1 ] || return 0
  declare -A keep=() week=() month=()
  count="${#names[@]}"
  for ((index = count - 1; index >= 0 && index >= count - BACKUP_KEEP_DAILY; index--)); do keep["${names[index]}"]=1; done
  for ((index = count - 1; index >= 0; index--)); do
    name="${names[index]}"; stamp="${name:0:10}"
    bucket="$(date -d "${stamp}" +%G-%V 2>/dev/null)"
    if [ -n "${bucket}" ] && [ -z "${week[${bucket}]:-}" ] && [ "${#week[@]}" -lt "${BACKUP_KEEP_WEEKLY}" ]; then
      week["${bucket}"]=1; keep["${name}"]=1
    fi
    bucket="${stamp:0:7}"
    if [ -z "${month[${bucket}]:-}" ] && [ "${#month[@]}" -lt "${BACKUP_KEEP_MONTHLY}" ]; then
      month["${bucket}"]=1; keep["${name}"]=1
    fi
  done
  for name in "${names[@]}"; do
    [ -n "${keep[${name}]:-}" ] && continue
    { btrfs subvolume delete "${dir}/${name}" >/dev/null 2>&1 || rm -rf "${dir:?}/${name}"; } &&
      echo "[${BACKUP_STAGE}] pruned [${dir}/${name}] outside the grandfather-father-son window"
  done
}

backup_document() {
  local state="$1" success="$2" started="$3" expires="${4:-}"
  local finished; finished="$(date --iso-8601=seconds)"
  local expires_ts=""
  [ -n "${expires}" ] && expires_ts="$(date --iso-8601=seconds -d @"${expires}" 2>/dev/null)"
  local duration=$(( $(date +%s) - started ))
  cat >"${BACKUP_STAGE_DIR}/status.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "state": "${state}",
  "trigger": "${BACKUP_TRIGGER}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "${finished}",
  "expires_ts": "${expires_ts}",
  "duration_s": ${duration},
  "success_bool": ${success},
  "disk_usage_perc": ${BACKUP_USAGE:-0},
  "file_count": ${BACKUP_FILES},
  "size_mb": ${BACKUP_SIZE},
  "files_held": ${BACKUP_FILES_HELD},
  "files_created": ${BACKUP_FILES_CREATED},
  "files_deleted": ${BACKUP_FILES_DELETED},
  "size_held_mb": ${BACKUP_SIZE_HELD},
  "sent_mb": ${BACKUP_SENT}
}
JSON
  mv "${BACKUP_STAGE_DIR}/status.json.tmp" "${BACKUP_STAGE_DIR}/status.json"
  backup_publish "supervisor/${BACKUP_HOST}/backup/stage/${BACKUP_STAGE}/status" "$(cat "${BACKUP_STAGE_DIR}/status.json")"
}

backup_settle() {
  [ -n "${BACKUP_HEARTBEAT_PID}" ] || return 0
  kill "${BACKUP_HEARTBEAT_PID}" 2>/dev/null
  wait "${BACKUP_HEARTBEAT_PID}" 2>/dev/null
  BACKUP_HEARTBEAT_PID=""
}

backup_heartbeat() {
  local hard=0
  [ "${BACKUP_TIMEOUT_HOURS}" -gt 0 ] 2>/dev/null && hard=$(( BACKUP_STARTED + BACKUP_TIMEOUT_HOURS * 3600 ))
  while :; do
    sleep "${BACKUP_HEARTBEAT_REFRESH}"
    local now; now="$(date +%s)"
    if [ "${hard}" -gt 0 ] && [ "${now}" -ge "${hard}" ]; then
      backup_document "running" false "${BACKUP_STARTED}" "$(( now - 1 ))"
      echo "[${BACKUP_STAGE}] exceeded BACKUP_TIMEOUT_HOURS [${BACKUP_TIMEOUT_HOURS}], signalling supervisor to reap" >&2
      return 0
    fi
    backup_document "running" false "${BACKUP_STARTED}" "$(( now + BACKUP_HEARTBEAT_GRACE ))"
  done
}
