#!/usr/bin/env bash

# Runs one stage of a backup run, from the supervisor probe or by hand, the same path both sides.
#
#   backup.sh <all|primary|secondary|tertiary> [start|stop] [run-id]
#   backup.sh tail [run-id]
#
# all is the hand entry point - it runs the stages this host owns, in order, under one run id, so a
# hand run has the same shape as the probe's and nothing has to adopt anything. tertiary joins only
# where fstab declares a /backup, since it is the one stage a host without a backup disk cannot run.
#
# tail follows a run that is already going, defaulting to the newest, tailing all three stage logs
# as one stream and printing each stage's status document once nothing is running any more. It reads
# and never writes, so it is safe beside a live run and any number may tail at once.
#
# Stages of one run share a run id, a stage reading what the earlier stages of that run recorded. A
# hand run that gives none mints a new id per invocation, so secondary would see no primary at all -
# it therefore adopts the newest run that did record one, and says which. It only ever adopts a
# service list, never data, so this cannot happen under the probe, where primary ran in this run.
# start heartbeats a status document and exits on the stage result, detaching only on a hand run,
# never under the probe, which owns the redirection and reads that status. A hand start detaches and
# then tails its own run, so the terminal follows the stage it just began and exits on its result -
# interrupting the tail leaves the stage running, since a tail only ever reads. stop is idempotent
# and never unmounts a share, and by hand it waits for the run to settle, bounded by
# BACKUP_STOP_SECONDS, then prints the same final status a tail ends with.
#
# A run holds BACKUP_LOCK for its whole life, so a hand run and the scheduled run cannot overlap -
# except under the probe, which holds the same lock across all three stages and would deadlock itself.
#
# Every stage writes one log, at BACKUP_STAGE_DIR/output.log, and echoes it to stdout as it goes -
# except under the probe, where stdout already is that file and a tee would write every line twice.
# Lines are stamped, levelled and prefixed with the stage, so a stage log reads on its own and the
# three concatenate in run order. Set BACKUP_QUIET=1 to keep the file and drop the stdout copy.
#
# The run owns identity, roots, retention window and timeout as BACKUP_* and a stage only reads them.
# A stage provides <stage>_start and <stage>_stop, reached through stage_start and stage_stop, and
# reports its work by adding to BACKUP_USAGE and the BACKUP_FILES/SIZE counters, directly or
# through backup_count.
#
# primary   never reads a data directory or knows a backup format, the module's own backup.sh owns
#           both, and a service is enrolled by shipping one. It records one status document per
#           service under BACKUP_SERVICE_PATH, which is what secondary reads back.
# secondary is additive and never deletes, mounts the share on demand and never unmounts it, and
#           delegates thinning to the service, falling back to backup_thin for one shipping none. It
#           promotes a service's whole backup directory, so the run id it reads chooses which
#           services to promote and never which bytes, and adopting an older run's list is safe.
# tertiary  is server hosts only, mirrors each locally-owned share whole - media and service homes,
#           not just backups - guarded on both mounts, and brings the disk up and down around itself.

set -uo pipefail

BACKUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_STAGE="${1:-}"
BACKUP_PHASE="${2:-start}"

case "${BACKUP_STAGE}/${BACKUP_PHASE}" in
all/start | all/stop | primary/start | primary/stop | secondary/start | secondary/stop | tertiary/start | tertiary/stop | tail/*) ;;
*)
  echo "Usage: ${0} <all|primary|secondary|tertiary> [start|stop] [run-id]" >&2
  echo "       ${0} tail [run-id]" >&2
  exit 2
  ;;
esac

BACKUP_RUN_ID="${3:-${BACKUP_RUN_ID:-$(date +%Y-%m-%d_%H-%M-%S)}}"
BACKUP_TRIGGER="${BACKUP_TRIGGER:-manual}"
[ -n "${BACKUP_RUN_ID_PASSED:-}" ] && BACKUP_TRIGGER="scheduled"
BACKUP_INSTALL_ROOT="${BACKUP_INSTALL_ROOT:-/var/lib/asystem/install}"
BACKUP_HOME_ROOT="${BACKUP_HOME_ROOT:-/home/asystem}"
BACKUP_RUN_PATH="${BACKUP_RUN_PATH:-${BACKUP_HOME_ROOT}/supervisor/backup/${BACKUP_RUN_ID}}"
BACKUP_STAGE_DIR="${BACKUP_RUN_PATH}/stage/${BACKUP_STAGE}"
BACKUP_SERVICE_PATH="${BACKUP_RUN_PATH}/stage/primary/service"
BACKUP_LOG="${BACKUP_STAGE_DIR}/output.log"
BACKUP_LOCK="$(dirname "${BACKUP_RUN_PATH}")/.lock"
BACKUP_CONFIG="${BACKUP_INSTALL_ROOT}/supervisor/latest/image/config.json"

backup_tail() {
  local base run path stage logs=() tail_pid="" sequence="${2:-}"
  base="$(dirname "${BACKUP_RUN_PATH}")"
  run="${1:-}"
  [ "${run}" = "start" ] && run=""
  [ -n "${run}" ] || run="$(find "${base}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -1)"
  [ -n "${run}" ] || { echo "No backup run found under [${base}]" >&2; return 1; }
  path="${base}/${run}"
  [ -d "${path}" ] || { echo "No backup run at [${path}]" >&2; return 1; }
  echo && echo "Backup tail [${run}] under [${path}]" && echo
  for stage in primary secondary tertiary; do logs+=("${path}/stage/${stage}/output.log"); done
  tail -n +1 -F -q "${logs[@]}" 2>/dev/null &
  tail_pid=$!
  backup_await "${path}" "" "${sequence}"
  kill "${tail_pid}" 2>/dev/null
  wait "${tail_pid}" 2>/dev/null
  backup_status "${path}"
}

backup_sequence() {
  local stage result=0 started sequence stages=(primary secondary)
  [ -n "$(backup_targets)" ] && stages+=(tertiary)
  echo && echo "Backup ${BACKUP_PHASE} [${BACKUP_RUN_ID}] over [${stages[*]}]"
  if [ "${BACKUP_PHASE}" = "stop" ]; then
    for stage in "${stages[@]}"; do
      BACKUP_DETACHED=1 "$0" "${stage}" stop "${BACKUP_RUN_ID}" || result=$?
    done
    backup_status "${BACKUP_RUN_PATH}" || result=1
    return "${result}"
  fi
  started="$(date +%s)"
  (
    for stage in "${stages[@]}"; do
      BACKUP_DETACHED=1 "$0" "${stage}" start "${BACKUP_RUN_ID}" || exit 1
    done
  ) &
  sequence=$!
  backup_tail "${BACKUP_RUN_ID}" "${sequence}" || result=1
  wait "${sequence}" || result=1
  backup_rollup "${started}"
  return "${result}"
}

backup_rollup() {
  local started="$1" stage doc run=0 failed=0 state=complete success=true
  for stage in primary secondary tertiary; do
    doc="${BACKUP_RUN_PATH}/stage/${stage}/status.json"
    [ -f "${doc}" ] || continue
    run=$(( run + 1 ))
    [ "$(backup_tail_field "${doc}" success_bool)" = "true" ] || failed=$(( failed + 1 ))
  done
  [ "${run}" -gt 0 ] || return 0
  if [ "${failed}" -gt 0 ]; then state=failed; success=false; fi
  cat >"${BACKUP_RUN_PATH}/status.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "state": "${state}",
  "trigger": "${BACKUP_TRIGGER}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "success_bool": ${success},
  "stages_run": ${run},
  "stages_failed": ${failed}
}
JSON
  mv "${BACKUP_RUN_PATH}/status.json.tmp" "${BACKUP_RUN_PATH}/status.json"
}

backup_running() {
  local pid
  while read -r pid; do
    [ -n "${pid}" ] || continue
    [ "${pid}" = "$$" ] && continue
    return 0
  done < <(pgrep -f "backup\.sh (primary|secondary|tertiary) (start|stop)" 2>/dev/null)
  return 1
}

backup_await() {
  local path="$1" stage doc deadline=0 sequence="${3:-}"
  [ -n "${2:-}" ] && deadline=$(( $(date +%s) + $2 ))
  while :; do
    sleep "${BACKUP_TAIL_POLL:-2}"
    [ "${deadline}" -gt 0 ] && [ "$(date +%s)" -ge "${deadline}" ] && return 1
    [ -n "${sequence}" ] && kill -0 "${sequence}" 2>/dev/null && continue
    backup_running && continue
    for stage in primary secondary tertiary; do
      doc="${path}/stage/${stage}/status.json"
      [ -f "${doc}" ] || continue
      [ "$(backup_tail_field "${doc}" state)" = "running" ] && continue 2
    done
    return 0
  done
}

backup_status() {
  local path="$1" stage doc state ok faults=0
  echo && echo "-- final status"
  for stage in primary secondary tertiary; do
    doc="${path}/stage/${stage}/status.json"
    if [ ! -f "${doc}" ]; then
      echo "   [${stage}] never started"
      continue
    fi
    state="$(backup_tail_field "${doc}" state)"
    ok="$(backup_tail_field "${doc}" success_bool)"
    if [ "${state}" = "complete" ] && [ "${ok}" = "true" ]; then
      echo "✅ [${stage}] [${state}] in [$(backup_tail_field "${doc}" duration_s)] s, files [$(backup_tail_field "${doc}" file_count)], size [$(backup_tail_field "${doc}" size_mb)] MB"
    else
      echo "❌ [${stage}] [${state}] in [$(backup_tail_field "${doc}" duration_s)] s, see [${path}/stage/${stage}/output.log]"
      faults=$(( faults + 1 ))
    fi
    sed 's/^/   /' "${doc}"
  done
  echo
  [ "${faults}" -eq 0 ] || return 1
  return 0
}

backup_tail_field() {
  jq -r --arg field "${2}" '.[$field] // empty' "${1}" 2>/dev/null
}

if [ "${BACKUP_STAGE}" = "tail" ]; then
  backup_tail "${BACKUP_PHASE}"
  exit $?
fi

[ "${BACKUP_STAGE}" = "all" ] || mkdir -p "${BACKUP_STAGE_DIR}"

BACKUP_ENV="${BACKUP_INSTALL_ROOT}/supervisor/latest/.env"
# shellcheck disable=SC1090
if [ -f "${BACKUP_ENV}" ]; then set -a; . "${BACKUP_ENV}"; set +a; fi
BACKUP_HOST="${SUPERVISOR_HOST:-$(hostname)}"

backup_stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

backup_log() {
  local level="$1"; shift
  local line; line="$(printf '%s [%-9s] %-5s %s' "$(backup_stamp)" "${BACKUP_STAGE}" "${level}" "$*")"
  case "${level}" in
  WARN | ERROR) printf '%s\n' "${line}" >&2 ;;
  *) printf '%s\n' "${line}" ;;
  esac
}

backup_banner() {
  local title="$1"; shift
  backup_log INFO "${title}"
  local field
  for field in "$@"; do backup_log INFO "  ${field}"; done
}

backup_elapsed() {
  local seconds="$1"
  printf '%02dh%02dm%02ds' $(( seconds / 3600 )) $(( seconds % 3600 / 60 )) $(( seconds % 60 ))
}

backup_rsync() {
  local capture="${BACKUP_STAGE_DIR}/.rsync-$$.out" status
  rsync "$@" 2>&1 | tee "${capture}"
  status="${PIPESTATUS[0]}"
  BACKUP_RSYNC_OUTPUT="$(cat "${capture}" 2>/dev/null)"
  rm -f "${capture}"
  return "${status}"
}

backup_config() {
  local value
  value="$(jq -r "${1} // empty" "${BACKUP_CONFIG}" 2>/dev/null)"
  printf '%s' "${value:-$2}"
}

backup_command() {
  local topic="$1" payload="$2"
  command -v mosquitto_pub >/dev/null 2>&1 || return 1
  [ -n "${BROKER_HOST:-}" ] || return 1
  mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT:-1883}" \
    ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -q 1 -t "${topic}" -m "${payload}" 2>/dev/null
}

backup_publish() {
  local topic="$1" payload="$2"
  command -v mosquitto_pub >/dev/null 2>&1 || return 0
  [ -n "${BROKER_HOST:-}" ] || return 0
  mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT:-1883}" \
    ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -q 1 -r -t "${topic}" -m "${payload}" 2>/dev/null || true
}

backup_mount() {
  local target="$1" error=""
  mountpoint -q "${target}" && return 0
  grep -qsE "^[^#][^[:space:]]*[[:space:]]+${target}[[:space:]]" /etc/fstab || {
    backup_log ERROR "mount of [${target}] refused, not mounted and not in /etc/fstab"
    return 1
  }
  backup_log INFO "mounting [${target}]"
  error="$(mount "${target}" 2>&1)" || ls "${target}" >/dev/null 2>&1 || true
  mountpoint -q "${target}" && return 0
  backup_log ERROR "mount of [${target}] failed with [${error:-no reason reported}]"
  return 1
}

backup_local() {
  case "$1" in ext4 | xfs | btrfs | f2fs) return 0 ;; *) return 1 ;; esac
}

backup_shares() {
  awk '$1 !~ /^#/ && $2 ~ /^\/share\/[0-9]+$/ { print $2, $3 }' /etc/fstab | sort -u
}

backup_mounted() {
  local mount source fstype
  findmnt -rn -o TARGET,SOURCE,FSTYPE 2>/dev/null | while read -r mount source fstype; do
    [[ "${mount}" =~ ^/share/[0-9]+$ ]] || continue
    backup_local "${fstype}" || continue
    case "${source}" in /dev/*) printf '%s\n' "${mount}" ;; esac
  done | sort -u
}

backup_promoted() {
  local status
  for status in "${BACKUP_SERVICE_PATH}"/*/status.json; do
    [ -f "${status}" ] || continue
    [ "$(jq -r '.success_bool // false' "${status}" 2>/dev/null)" = "true" ] &&
      basename "$(dirname "${status}")"
  done
}

backup_adopted() {
  local base run
  base="$(dirname "${BACKUP_RUN_PATH}")"
  while read -r run; do
    [ -d "${base}/${run}/stage/primary/service" ] && { echo "${run}"; return 0; }
  done < <(find "${base}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r)
  return 1
}

backup_demoted() {
  local status
  for status in "${BACKUP_SERVICE_PATH}"/*/status.json; do
    [ -f "${status}" ] || continue
    [ "$(jq -r '.success_bool // false' "${status}" 2>/dev/null)" = "true" ] ||
      basename "$(dirname "${status}")"
  done
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

backup_transferred() {
  local verb="$1" what="$2" started="$3"
  backup_count "${BACKUP_RSYNC_OUTPUT}"
  backup_log INFO "${verb} [${what}] in [$(backup_elapsed $(( $(date +%s) - started )))], running total [${BACKUP_FILES}] files, [${BACKUP_SIZE}] MB"
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
      backup_log INFO "pruned [${name}] from [${dir}] outside the grandfather father son window"
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
  local hard=0 nap=""
  trap '[ -n "${nap}" ] && kill "${nap}" 2>/dev/null; exit 0' TERM
  [ "${BACKUP_TIMEOUT_HOURS}" -gt 0 ] 2>/dev/null && hard=$(( BACKUP_STARTED + BACKUP_TIMEOUT_HOURS * 3600 ))
  while :; do
    sleep "${BACKUP_HEARTBEAT_REFRESH}" &
    nap=$!
    wait "${nap}"
    nap=""
    local now; now="$(date +%s)"
    if [ "${hard}" -gt 0 ] && [ "${now}" -ge "${hard}" ]; then
      backup_document "running" false "${BACKUP_STARTED}" "$(( now - 1 ))"
      backup_log ERROR "exceeded the timeout of [${BACKUP_TIMEOUT_HOURS}] hours, terminating [${BACKUP_STAGE}]"
      stage_stop || true
      kill -TERM "${BACKUP_MAIN_PID}" 2>/dev/null
      return 0
    fi
    backup_log INFO "heartbeat after [$(backup_elapsed $(( now - BACKUP_STARTED )))], files [${BACKUP_FILES}], size [${BACKUP_SIZE}] MB"
    backup_document "running" false "${BACKUP_STARTED}" "$(( now + BACKUP_HEARTBEAT_GRACE ))"
  done
}

primary_start() {
  local service script running health failed=0 count=0 index=0 enrolled=() configured=()
  mapfile -t configured < <(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .services[]' "${BACKUP_CONFIG}" 2>/dev/null)
  for service in "${configured[@]}"; do
    [ -x "${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh" ] && enrolled+=("${service}")
  done
  backup_log INFO "configured [${#configured[@]}] services, of which [${#enrolled[@]}] ship a backup.sh"
  for service in "${enrolled[@]}"; do
    index=$(( index + 1 ))
    script="${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh"
    running="$(docker ps --filter "name=^/${service}$" --filter "status=running" --format '{{.Names}}')"
    if [ "${running}" != "${service}" ]; then
      backup_log WARN "skipped [${service}] [${index}/${#enrolled[@]}], container is not running"
      continue
    fi
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${service}" 2>/dev/null)"
    if [ "${health}" = "starting" ]; then
      backup_log WARN "skipped [${service}] [${index}/${#enrolled[@]}], container is still starting"
      continue
    fi
    count=$(( count + 1 ))
    local dir="${BACKUP_SERVICE_PATH}/${service}"
    mkdir -p "${dir}"
    local started; started="$(date +%s)"
    local previous; previous="$(find "${BACKUP_HOME_ROOT}/${service}/backup" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | tail -1)"
    backup_log INFO "backing up [${service}] [${index}/${#enrolled[@]}] with [${script}], logging to [${dir}/output.log]"
    local rc=0
    BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}" BACKUP_SERVICE_RESTART=true BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS}" \
      bash "${script}" >"${dir}/output.log" 2>&1 || rc=$?
    local state=complete ok=true
    [ "${rc}" -eq 0 ] || { state=failed; ok=false; failed=$(( failed + 1 )); }
    local newest size=0 files=0 kind=unknown version=unknown stamp file stem
    newest="$(find "${BACKUP_HOME_ROOT}/${service}/backup" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | tail -1)"
    [ "${state}" = complete ] && [ "${newest}" = "${previous}" ] && state=skipped
    if [ -n "${newest}" ]; then
      size="$(du -m -s "${newest}" 2>/dev/null | cut -f1)"
      size="${size:-0}"
      files="$(find "${newest}" -type f 2>/dev/null | wc -l | tr -d ' ')"
      stamp="$(basename "${newest}")"
      file="$(find "${newest}" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort | head -1)"
      case "${file}" in *_delta.*) kind="delta" ;; *_full.*) kind="full" ;; esac
      stem="${file%%_delta.*}"
      stem="${stem%%_full.*}"
      case "${stem}" in
      *_from_*) version="${stem##*_from_}" ;;
      *) version="${stem#"${service}_${stamp}_"}" ;;
      esac
      if [ -z "${version}" ] || [ "${version}" = "${stem}" ]; then version=unknown; fi
    fi
    cat >"${dir}/status.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "backup_id": "$(basename "${newest:-none}")",
  "state": "${state}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "success_bool": ${ok},
  "kind": "${kind}",
  "version": "${version}",
  "file_count": ${files:-0},
  "size_mb": ${size:-0}
}
JSON
    mv "${dir}/status.json.tmp" "${dir}/status.json"
    backup_log "$([ "${ok}" = true ] && echo INFO || echo ERROR)" \
      "finished [${service}] as [${state}] in [$(backup_elapsed $(( $(date +%s) - started )))], kind [${kind}], version [${version}], files [${files:-0}], size [${size:-0}] MB"
    BACKUP_FILES=$(( BACKUP_FILES + files ))
    BACKUP_SIZE=$(( BACKUP_SIZE + size ))
    [ "${state}" = complete ] && BACKUP_FILES_CREATED=$(( BACKUP_FILES_CREATED + 1 ))
    backup_publish "supervisor/${BACKUP_HOST}/backup/stage/primary/service/${service}/status" "$(cat "${dir}/status.json")"
  done
  backup_log INFO "attempted [${count}] services with [${failed}] failed"
  backup_usage "${BACKUP_HOME_ROOT}"
  return "${failed}"
}

primary_stop() {
  backup_log INFO "terminating any running service backup.sh"
  pkill -TERM -f "${BACKUP_INSTALL_ROOT}/[a-z0-9_-]*/latest/backup.sh" 2>/dev/null || true
}

secondary_start() {
  local share index service adopted="" failed=0 promote=() demoted=() total=0 promoted=0
  index="$(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .index // empty' "${BACKUP_CONFIG}" 2>/dev/null)"
  if [ -n "${index}" ]; then
    share="/share/${index}0"
  else
    share="$(backup_shares | awk '{ print $1 }' |
      while read -r mount; do mountpoint -q "${mount}" && { echo "${mount}"; break; }; done)"
  fi
  [ -n "${share}" ] || { backup_log ERROR "no share destination resolved for host [${BACKUP_HOST}]"; return 1; }
  backup_log INFO "resolved share [${share}] from [${index:-fstab}]"
  backup_mount "${share}" || return 1
  mkdir -p "${share}/backup"
  if [ ! -d "${BACKUP_RUN_PATH}/stage/primary" ]; then
    adopted="$(backup_adopted)"
    if [ -n "${adopted}" ]; then
      BACKUP_SERVICE_PATH="$(dirname "${BACKUP_RUN_PATH}")/${adopted}/stage/primary/service"
      backup_log INFO "run [${BACKUP_RUN_ID}] ran no primary, adopting the service list of run [${adopted}] from [${BACKUP_SERVICE_PATH}]"
    else
      backup_log WARN "run [${BACKUP_RUN_ID}] ran no primary and no earlier run under [$(dirname "${BACKUP_RUN_PATH}")] recorded one"
    fi
  fi
  mapfile -t promote < <(printf 'supervisor\n'; backup_promoted)
  mapfile -t demoted < <(backup_demoted)
  total="${#promote[@]}"
  for service in "${demoted[@]}"; do
    backup_log WARN "not promoting [${service}], its primary backup did not succeed in run [${adopted:-${BACKUP_RUN_ID}}]"
  done
  if [ "${total}" -eq 1 ]; then
    backup_log WARN "run [${adopted:-${BACKUP_RUN_ID}}] recorded no successful service backup under [${BACKUP_SERVICE_PATH}], promoting [supervisor] alone"
  fi
  backup_log INFO "promoting [${total}] services to [${share}/backup]"
  for service in "${promote[@]}"; do
    promoted=$(( promoted + 1 ))
    local source="${BACKUP_HOME_ROOT}/${service}/backup/"
    local target="${share}/backup/${service}"
    if [ ! -d "${source}" ]; then
      backup_log WARN "skipped [${service}] [${promoted}/${total}], no backup directory at [${source}]"
      continue
    fi
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -delete 2>/dev/null
    backup_log INFO "promoting [${service}] [${promoted}/${total}] from [${source}] to [${target}]"
    local started; started="$(date +%s)"
    backup_rsync -a --stats --human-readable --out-format='%t %o %f %l' \
      --exclude '/.lock' --exclude '.rsync/' --exclude '.rsync-*' \
      --temp-dir="${target}/.rsync" -- "${source}" "${target}/" || failed=1
    backup_transferred "promoted" "${service}" "${started}"
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

secondary_stop() {
  backup_log INFO "terminating any running promotion rsync"
  pkill -TERM -f "rsync .*${BACKUP_HOME_ROOT}" 2>/dev/null || true
}

backup_ready() {
  local source fstype
  read -r fstype source < <(findmnt -M /backup -n -o FSTYPE,SOURCE 2>/dev/null) || return 1
  backup_local "${fstype}" || return 1
  case "${source}" in /dev/*) return 0 ;; *) return 1 ;; esac
}

backup_targets() {
  awk '$1 !~ /^#/ && ($2 == "/backup" || $2 ~ /^\/backup\//) { print $2 }' /etc/fstab
}

backup_attach() {
  local deadline=$(( $(date +%s) + BACKUP_DISK_SECONDS )) started target device pending failed=0
  started="$(date +%s)"
  backup_log INFO "waiting up to [${BACKUP_DISK_SECONDS}] s for [$(backup_targets | xargs)] to enumerate, polling every [${BACKUP_DISK_POLL}] s"
  while :; do
    pending=0
    while read -r target; do
      device="$(awk -v mp="${target}" '$1 !~ /^#/ && $2 == mp { print $1 }' /etc/fstab)"
      case "${device}" in
      PARTLABEL=*) [ -e "/dev/disk/by-partlabel/${device#PARTLABEL=}" ] || pending=1 ;;
      PARTUUID=*) [ -e "/dev/disk/by-partuuid/${device#PARTUUID=}" ] || pending=1 ;;
      UUID=*) [ -e "/dev/disk/by-uuid/${device#UUID=}" ] || pending=1 ;;
      LABEL=*) [ -e "/dev/disk/by-label/${device#LABEL=}" ] || pending=1 ;;
      /dev/*) [ -b "${device}" ] || pending=1 ;;
      *) : ;;
      esac
    done < <(backup_targets)
    [ "${pending}" -eq 0 ] && break
    if [ "$(date +%s)" -ge "${deadline}" ]; then
      backup_log ERROR "timed out after [${BACKUP_DISK_SECONDS}] s waiting for the backup disk to enumerate, check the disk is powered"
      return 1
    fi
    sleep "${BACKUP_DISK_POLL}"
  done
  backup_log INFO "backup disk enumerated after [$(( $(date +%s) - started ))] s"
  while read -r target; do
    backup_mount "${target}" || failed=1
  done < <(backup_targets)
  return "${failed}"
}

backup_detach() {
  local target
  while read -r target; do
    mountpoint -q "${target}" || continue
    sync
    umount "${target}" || umount -l "${target}" || backup_log WARN "could not unmount [${target}]"
  done < <(backup_targets)
}

backup_scrub_counter() {
  local value
  value="$(printf '%s\n' "$1" | sed -n "s/^[[:space:]]*$2:[[:space:]]*//p" | head -1 | tr -dc '0-9')"
  printf '%s' "${value:-0}"
}

backup_scrub_document() {
  local state="$1" success="$2" started="$3" scrubbed="$4" progress="$5" found="$6" corrected="$7" uncorrectable="$8"
  local files="${9:-}" count="${10:-0}"
  mkdir -p "${BACKUP_STAGE_DIR}"
  cat >"${BACKUP_STAGE_DIR}/scrub.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "state": "${state}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "success_bool": ${success},
  "scrubbed_mb": ${scrubbed},
  "progress_perc": ${progress},
  "errors_found": ${found},
  "errors_corrected": ${corrected},
  "errors_uncorrectable": ${uncorrectable},
  "files_to_delete": "${files}",
  "files_to_delete_count": ${count}
}
JSON
  mv "${BACKUP_STAGE_DIR}/scrub.json.tmp" "${BACKUP_STAGE_DIR}/scrub.json"
  backup_publish "supervisor/${BACKUP_HOST}/backup/stage/tertiary/scrub/status" "$(cat "${BACKUP_STAGE_DIR}/scrub.json")"
}

backup_scrub_corrupt() {
  dmesg 2>/dev/null | tail -n "+$(( ${1:-0} + 1 ))" |
    grep -oE '\(path: [^)]+\)' | sed -e 's/^(path: //' -e 's/)$//' | sort -u
}

backup_scrub_cancel() {
  command -v btrfs >/dev/null 2>&1 || return 0
  mountpoint -q /backup || return 0
  btrfs scrub cancel /backup >/dev/null 2>&1 || true
}

backup_scrub() {
  local status raw action started hard since state=finished success=true
  local scrubbed=0 progress=0 found=0 corrected=0 uncorrectable=0
  local kernel=0 files="" count=0
  started="$(date +%s)"
  if ! command -v btrfs >/dev/null 2>&1; then
    backup_log WARN "scrub skipped, no [btrfs] on the PATH"
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  if ! btrfs filesystem show /backup >/dev/null 2>&1; then
    backup_log INFO "scrub skipped, [/backup] is not btrfs"
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  status="$(btrfs scrub status /backup 2>/dev/null)"
  case "${status}" in
  *interrupted* | *aborted*) action="resume" ;;
  *)
    action="start"
    since="$(printf '%s\n' "${status}" | sed -n 's/^Scrub started:[[:space:]]*//p' | head -1)"
    if [ -n "${since}" ] &&
      [ "$(date -d "${since}" +%s 2>/dev/null || echo 0)" -gt "$(( started - BACKUP_SCRUB_DAYS * 86400 ))" ]; then
      backup_log INFO "scrub skipped, the last pass started [${since}] within [${BACKUP_SCRUB_DAYS}] days"
      backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
      return 0
    fi
    ;;
  esac
  hard=0
  [ "${BACKUP_TIMEOUT_HOURS}" -gt 0 ] 2>/dev/null &&
    hard=$(( BACKUP_STARTED + BACKUP_TIMEOUT_HOURS * 3600 - BACKUP_SCRUB_MARGIN ))
  [ "${hard}" -gt 0 ] || hard=$(( started + 3600 ))
  if [ "${hard}" -le "${started}" ]; then
    backup_log WARN "scrub skipped, no time left inside the stage timeout"
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  kernel="$(dmesg 2>/dev/null | wc -l)"
  backup_log INFO "scrub [${action}] on [/backup] until [$(date --iso-8601=seconds -d @"${hard}")], polling every [${BACKUP_SCRUB_POLL}] s"
  if ! btrfs scrub "${action}" -c 3 -n 15 /backup >/dev/null 2>&1; then
    backup_log ERROR "could not [${action}] the scrub on [/backup]"
    backup_scrub_document "failed" false "${started}" 0 0 0 0 0
    return 1
  fi
  while :; do
    sleep "${BACKUP_SCRUB_POLL}"
    raw="$(btrfs scrub status -R /backup 2>/dev/null)"
    backup_log INFO "scrub at [$(printf '%s\n' "$(btrfs scrub status /backup 2>/dev/null)" | sed -n 's/.*(\([0-9.]*\)%).*/\1/p' | head -1)] pct, scrubbed [$(( $(backup_scrub_counter "${raw}" "data_bytes_scrubbed") / 1048576 ))] MB"
    printf '%s\n' "${raw}" | grep -qi "status:[[:space:]]*running" || break
    if [ "$(date +%s)" -ge "${hard}" ]; then
      btrfs scrub cancel /backup >/dev/null 2>&1 || true
      state="interrupted"
      break
    fi
  done
  raw="$(btrfs scrub status -R /backup 2>/dev/null)"
  status="$(btrfs scrub status /backup 2>/dev/null)"
  scrubbed=$(( $(backup_scrub_counter "${raw}" "data_bytes_scrubbed") / 1048576 ))
  corrected="$(backup_scrub_counter "${raw}" "corrected_errors")"
  uncorrectable="$(backup_scrub_counter "${raw}" "uncorrectable_errors")"
  found=$(( $(backup_scrub_counter "${raw}" "csum_errors") +
    $(backup_scrub_counter "${raw}" "verify_errors") +
    $(backup_scrub_counter "${raw}" "super_errors") ))
  progress="$(printf '%s\n' "${status}" | sed -n 's/.*(\([0-9.]*\)%).*/\1/p' | head -1)"
  progress="${progress:-0}"
  case "${status}" in
  *aborted*) state="failed" ;;
  *interrupted*) state="interrupted" ;;
  esac
  if [ "${found}" -gt 0 ] || [ "${uncorrectable}" -gt 0 ]; then
    success=false
    count="$(backup_scrub_corrupt "${kernel}" | wc -l | tr -d ' ')"
    files="$(backup_scrub_corrupt "${kernel}" | head -20 | paste -sd ',' - | sed 's/"/\\"/g')"
    {
      printf '%s\n\n' "${raw}"
      backup_scrub_corrupt "${kernel}"
      printf '\n'
      dmesg -T 2>/dev/null | tail -n "+$(( kernel + 1 ))" |
        grep -iE 'btrfs.*(csum|checksum|unable to fixup)' | tail -500
    } >"${BACKUP_STAGE_DIR}/scrub.log"
    backup_log ERROR "scrub found [${found}] errors with [${uncorrectable}] uncorrectable across [${count}] files, delete them and re-mirror, listed in [${BACKUP_STAGE_DIR}/scrub.log]"
  else
    backup_log INFO "scrub [${state}] at [${progress}] pct having scrubbed [${scrubbed}] MB with no errors"
  fi
  backup_scrub_document "${state}" "${success}" "${started}" "${scrubbed}" "${progress}" "${found}" "${corrected}" "${uncorrectable}" "${files}" "${count}"
  [ "${success}" = "true" ]
}

tertiary_start() {
  local share index target failed=0 fstab_target fstab_type command_topic
  command_topic="$(backup_config '.asystem.backup.command_topic' '')"
  if [ -n "${command_topic}" ]; then
    backup_log INFO "powering the backup disk on with [ON] to [${command_topic}]"
    backup_command "${command_topic}" "ON" ||
      backup_log WARN "could not publish [ON] to [${command_topic}], the disk must already be powered"
  fi
  if ! backup_attach; then
    backup_log ERROR "backup disk did not come up"
    return 1
  fi
  if ! backup_ready; then
    backup_log ERROR "[/backup] is not a mounted local filesystem, refusing to mirror"
    return 1
  fi
  while read -r fstab_target fstab_type; do
    backup_local "${fstab_type}" || continue
    backup_mount "${fstab_target}" || backup_log WARN "could not mount [${fstab_target}]"
  done < <(backup_shares)
  while read -r share; do
    index="${share#/share/}"
    [[ "${index}" =~ ^[0-9]+$ ]] || continue
    target="/backup/share/${index}"
    mountpoint -q "${share}" || { backup_log ERROR "[${share}] vanished mid-run, skipping"; failed=1; continue; }
    mountpoint -q /backup || { backup_log ERROR "[/backup] vanished mid-run, aborting"; failed=1; break; }
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -mtime +7 -delete 2>/dev/null
    backup_log INFO "mirroring [${share}] to [${target}]"
    local started; started="$(date +%s)"
    backup_rsync -a --delete --stats --human-readable --out-format='%t %o %f %l' \
      --exclude '/tmp/' --exclude '.rsync/' --exclude '.rsync-*' --exclude '/.lock' \
      --partial-dir="${target}/.rsync" -- "${share}/" "${target}/" || failed=1
    backup_transferred "mirrored" "${share}" "${started}"
  done < <(backup_mounted)
  if mountpoint -q /backup; then
    if command -v btrfs >/dev/null 2>&1 && backup_ready; then
      local subvolume name snapshots="/backup/.snapshots"
      for subvolume in /backup/share/*; do
        [ -d "${subvolume}" ] || continue
        btrfs subvolume show "${subvolume}" >/dev/null 2>&1 || continue
        name="$(basename "${subvolume}")"
        mkdir -p "${snapshots}/share/${name}"
        btrfs subvolume snapshot -r "${subvolume}" "${snapshots}/share/${name}/${BACKUP_RUN_ID}" >/dev/null 2>&1 &&
          backup_log INFO "snapshotted [${subvolume}] to [${snapshots}/share/${name}/${BACKUP_RUN_ID}]"
        backup_thin "${snapshots}/share/${name}"
      done
    fi
    backup_scrub || failed=1
    backup_usage /backup
  fi
  tertiary_stop || true
  return "${failed}"
}

tertiary_stop() {
  backup_log INFO "cancelling any scrub and unmounting the backup disk"
  backup_scrub_cancel
  pkill -TERM -f "rsync .*/backup/share" 2>/dev/null || true
  sync
  backup_detach
}

stage_start() {
  case "${BACKUP_STAGE}" in
  primary) primary_start ;;
  secondary) secondary_start ;;
  tertiary) tertiary_start ;;
  esac
}

stage_stop() {
  case "${BACKUP_STAGE}" in
  primary) primary_stop ;;
  secondary) secondary_stop ;;
  tertiary) tertiary_stop ;;
  esac
}

BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-$(backup_config '.asystem.backup.timeout_hours' 3)}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-$(backup_config '.asystem.backup.keep_daily' 7)}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-$(backup_config '.asystem.backup.keep_weekly' 4)}"
BACKUP_KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-$(backup_config '.asystem.backup.keep_monthly' 12)}"
BACKUP_HEARTBEAT_REFRESH="${BACKUP_HEARTBEAT_REFRESH:-600}"
BACKUP_HEARTBEAT_GRACE="${BACKUP_HEARTBEAT_GRACE:-3600}"
BACKUP_HEARTBEAT_PID=""
BACKUP_DISK_SECONDS="${BACKUP_DISK_SECONDS:-120}"
BACKUP_DISK_POLL="${BACKUP_DISK_POLL:-1}"
BACKUP_SCRUB_DAYS="${BACKUP_SCRUB_DAYS:-30}"
BACKUP_SCRUB_MARGIN="${BACKUP_SCRUB_MARGIN:-900}"
BACKUP_SCRUB_POLL="${BACKUP_SCRUB_POLL:-30}"

BACKUP_USAGE=0
BACKUP_FILES=0
BACKUP_FILES_HELD=0
BACKUP_FILES_CREATED=0
BACKUP_FILES_DELETED=0
BACKUP_SIZE=0
BACKUP_SIZE_HELD=0
BACKUP_SENT=0
BACKUP_RSYNC_OUTPUT=""

if [ "${BACKUP_STAGE}" = "all" ]; then
  backup_sequence
  exit $?
fi

if [ "${BACKUP_PHASE}" = "stop" ]; then
  exec 3>&1
  if [ -n "${BACKUP_RUN_ID_PASSED:-}" ] || [ -n "${BACKUP_QUIET:-}" ]; then
    exec >>"${BACKUP_LOG}" 2>&1
  else
    exec > >(tee -a "${BACKUP_LOG}") 2>&1
  fi
  backup_log INFO "stopping [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}]"
  stage_stop || true
  backup_log INFO "stopped [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}]"
  if [ -z "${BACKUP_RUN_ID_PASSED:-}" ]; then
    backup_await "${BACKUP_RUN_PATH}" "${BACKUP_STOP_SECONDS:-60}" ||
      backup_log WARN "[${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}] is still running after [${BACKUP_STOP_SECONDS:-60}] s"
    backup_status "${BACKUP_RUN_PATH}" >&3 || true
  fi
  exit 0
fi

if [ -z "${BACKUP_DETACHED:-}" ] && [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && { [ -t 1 ] || [ "${BACKUP_TIMEOUT_HOURS}" = "0" ]; }; then
  export BACKUP_DETACHED=1
  nohup "$0" "${BACKUP_STAGE}" start "${BACKUP_RUN_ID}" >>"${BACKUP_LOG}" 2>&1 &
  BACKUP_CHILD=$!
  disown
  backup_log INFO "detached [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}], following [${BACKUP_LOG}]"
  while kill -0 "${BACKUP_CHILD}" 2>/dev/null && [ ! -f "${BACKUP_STAGE_DIR}/status.json" ]; do sleep 1; done
  backup_tail "${BACKUP_RUN_ID}"
  exit $?
fi
if [ -z "${BACKUP_RUN_ID_PASSED:-}" ]; then
  if [ -n "${BACKUP_QUIET:-}" ] || [ -n "${BACKUP_DETACHED:-}" ]; then
    exec >>"${BACKUP_LOG}" 2>&1
  else
    exec > >(tee -a "${BACKUP_LOG}") 2>&1
  fi
fi

if [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && command -v flock >/dev/null 2>&1; then
  exec 9>>"${BACKUP_LOCK}"
  if ! flock -n 9; then
    backup_log ERROR "another backup run holds [${BACKUP_LOCK}], refusing to start [${BACKUP_STAGE}]"
    exit 3
  fi
fi

BACKUP_MAIN_PID=$$
BACKUP_STARTED="$(date +%s)"
trap 'backup_log WARN "interrupted, stopping [${BACKUP_STAGE}]"; stage_stop || true; backup_settle; backup_document "failed" false "${BACKUP_STARTED}"; exit 143' TERM INT
backup_banner "starting [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}]" \
  "host      [${BACKUP_HOST}]" \
  "trigger   [${BACKUP_TRIGGER}]" \
  "runner    [${BACKUP_ROOT}/$(basename "${BASH_SOURCE[0]}")]" \
  "log       [${BACKUP_LOG}]" \
  "run path  [${BACKUP_RUN_PATH}]" \
  "home root [${BACKUP_HOME_ROOT}]" \
  "installs  [${BACKUP_INSTALL_ROOT}]" \
  "config    [${BACKUP_CONFIG}]" \
  "timeout   [${BACKUP_TIMEOUT_HOURS}] hours" \
  "retention [${BACKUP_KEEP_DAILY}] daily, [${BACKUP_KEEP_WEEKLY}] weekly, [${BACKUP_KEEP_MONTHLY}] monthly" \
  "heartbeat [${BACKUP_HEARTBEAT_REFRESH}] s refresh, [${BACKUP_HEARTBEAT_GRACE}] s grace"
backup_document "running" false "${BACKUP_STARTED}" "$(( BACKUP_STARTED + BACKUP_HEARTBEAT_GRACE ))"
backup_heartbeat 9>&- &
BACKUP_HEARTBEAT_PID=$!

BACKUP_RESULT=0
stage_start || BACKUP_RESULT=$?
backup_settle
BACKUP_ELAPSED=$(( $(date +%s) - BACKUP_STARTED ))
if [ "${BACKUP_RESULT}" -eq 0 ]; then
  backup_document "complete" true "${BACKUP_STARTED}"
else
  backup_document "failed" false "${BACKUP_STARTED}"
fi
backup_banner "finished [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}] as [$([ "${BACKUP_RESULT}" -eq 0 ] && echo complete || echo failed)]" \
  "elapsed   [$(backup_elapsed "${BACKUP_ELAPSED}")]" \
  "files     [${BACKUP_FILES}] transferred, [${BACKUP_FILES_CREATED}] created, [${BACKUP_FILES_DELETED}] deleted, [${BACKUP_FILES_HELD}] held" \
  "size      [${BACKUP_SIZE}] MB transferred, [${BACKUP_SENT}] MB sent, [${BACKUP_SIZE_HELD}] MB held" \
  "disk      [${BACKUP_USAGE}] pct used" \
  "status    [${BACKUP_STAGE_DIR}/status.json]"
exit "${BACKUP_RESULT}"
