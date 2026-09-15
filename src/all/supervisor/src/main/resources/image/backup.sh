#!/usr/bin/env bash

# Runs one stage of a backup run, from the supervisor probe or by hand, the same path both sides.
# Usage: backup.sh help. Full design and rationale: src/build/resources/plans/backup.md.
#
# The run owns identity, roots, retention window, timeout and BACKUP_SCRUB/BACKUP_TRIGGER as BACKUP_*,
# and a stage only reads them. A stage provides <stage>_start and <stage>_stop, reached through
# stage_start and stage_stop, and reports its work by adding to BACKUP_USAGE and the BACKUP_FILES/SIZE
# counters, directly or through backup_count.
#
# A run holds BACKUP_LOCK for its whole life, so a hand run and the scheduled run cannot overlap - except
# under the probe, which holds the same lock across all three stages and would deadlock itself.
#
# Every stage writes one log at BACKUP_STAGE_DIR/output.log and echoes it to stdout as it goes - except
# under the probe, where stdout already is that file and a tee would write every line twice. Set
# BACKUP_QUIET=1 to keep the file and drop the stdout copy, and BACKUP_SOURCE_ONLY=1 to source this file
# for its functions alone, skipping the run and its side effects, which is how the unit tests reach them.
#
# Every stop sends SIGCONT before SIGTERM, because a process stopped by a signal cannot run its trap
# until continued. A module's own backup.sh is handed /dev/null on stdin, never the operator's terminal,
# and the stage sequence runs under set -m in a background process group, so anything that reads the
# terminal from down there is sent SIGTTIN and stopped rather than hanging silently.
#
# Every state a status document carries, and every plug command, is a BACKUP_STATE_*/BACKUP_COMMAND_*
# variable mirroring metric.BackupState*/Command* in src/main/go/supervisor/internal/metric/metric_schema.go
# - a unit test holds the two sets equal, so an addition here left undeclared there fails the build.
#
# primary   never reads a data directory or knows a backup format - the module's own backup.sh owns both.
# secondary is additive and never deletes, mounts the share on demand and never unmounts it.
# tertiary  mirrors each locally-owned share whole - media and service homes, not just backups - and
#           closes with a monthly btrfs scrub; a scrub fault never fails the stage, only a checksum or a
#           device error does.

set -uo pipefail

backup_line() {
  local level="$1" stage="$2"; shift 2
  printf '[%-4s %-9s %8s] %s\n' "${level}" "${stage}" "$(date '+%H:%M:%S')" "$*"
}

backup_log() {
  local level="$1"; shift
  [ "${level}" = "ERROR" ] && level=ERRS
  case "${level}" in
  WARN | ERRS) backup_line "${level}" "" "$*" >&2 ;;
  *) backup_line "${level}" "" "$*" ;;
  esac
}

backup_bounded() {
  local limit="$1" label="$2" root work pid waited=0 status
  shift 2
  root="${BACKUP_STAGE_DIR:-}"
  [ -d "${root}" ] || root="${TMPDIR:-/tmp}"
  BACKUP_BOUNDED_SEQ=$(( BACKUP_BOUNDED_SEQ + 1 ))
  work="${root}/.bounded-${BASHPID}-${BACKUP_BOUNDED_SEQ}"
  BACKUP_BOUNDED_OUTPUT=""
  rm -f "${work}.out" "${work}.rc"
  { "$@" >"${work}.out" 2>&1; printf '%s' "$?" >"${work}.tmp"; mv "${work}.tmp" "${work}.rc"; } &
  pid=$!
  while [ ! -s "${work}.rc" ]; do
    [ "${waited}" -ge "${limit}" ] && break
    sleep 1
    waited=$(( waited + 1 ))
  done
  if [ -s "${work}.rc" ]; then
    read -r status <"${work}.rc"
    BACKUP_BOUNDED_OUTPUT="$(cat "${work}.out" 2>/dev/null)"
    rm -f "${work}.out" "${work}.rc"
    return "${status:-0}"
  fi
  kill -KILL "${pid}" 2>/dev/null
  rm -f "${work}.out" "${work}.rc"
  backup_log WARN "abandoned [${label}] with no answer after [${limit}] s, it is blocked on a disk that stopped responding"
  return "${BACKUP_BOUNDED_ABANDONED}"
}

backup_announce() {
  backup_log INFO "starting run [${BACKUP_RUN_ID}] over [$1] as [${BACKUP_TRIGGER}] with scrub [$([ "${BACKUP_SCRUB}" = "1" ] && echo on || echo off)]"
}

BACKUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRUB="${BACKUP_SCRUB:-}"
BACKUP_SCRUB_FORCED="${BACKUP_SCRUB_FORCED:-0}"
BACKUP_SCRUB_DAY="${BACKUP_SCRUB_DAY:-1}"
BACKUP_SCRUB_WINDOW="${BACKUP_SCRUB_WINDOW:-3}"
BACKUP_BOUNDED_WAIT="${BACKUP_BOUNDED_WAIT:-60}"
BACKUP_BOUNDED_ABANDONED=124
BACKUP_BOUNDED_SEQ=0
BACKUP_BOUNDED_OUTPUT=""
BACKUP_USAGE_WEDGED=""
BACKUP_USAGE_UNIDENTIFIED=""
BACKUP_SCRUB_READING=""
BACKUP_STAGE="${BACKUP_STAGE:-all}"
BACKUP_SCRUB_ASKED=0
BACKUP_GIVEN=()
BACKUP_REJECT=""

backup_help() {
  local out=2
  [ "${1:-}" = "help" ] && out=1
  {
    echo "Usage: ${0##*/} [command] [argument] [options]"
    echo
    echo "  start   [run-id]  run this host's stages, minting a run id when given none"
    echo "  stop    [run-id]  stop a run, or every active one when given none"
    echo "  tail    [run-id]  follow a run, or the newest when given none"
    echo "  auto    [on|off]  turn switch reaper on or off, resets to on daily"
    echo "  list              list history of runs"
    echo "  help              this text, default command when given none"
    echo
    echo "  --stage <name>    execute one stage (primary|secondary|tertiary) only"
    echo "  --scrub           scrub the backup disk"
    echo "  --quiet           drop the stdout copy of the stage log"
  } >&"${out}"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
  --scrub) BACKUP_SCRUB=1; BACKUP_SCRUB_FORCED=1; BACKUP_SCRUB_ASKED=1 ;;
  --quiet) BACKUP_QUIET=1 ;;
  --stage) shift; BACKUP_STAGE="${1:-}" ;;
  --stage=*) BACKUP_STAGE="${1#*=}" ;;
  -*) BACKUP_REJECT="${1}" ;;
  *) BACKUP_GIVEN+=("$1") ;;
  esac
  shift
done
set -- ${BACKUP_GIVEN[@]+"${BACKUP_GIVEN[@]}"}
BACKUP_COMMAND="${1:-help}"
BACKUP_ARGUMENT="${2:-}"
BACKUP_RUN_GIVEN="${BACKUP_ARGUMENT}"
[ "${BACKUP_COMMAND}" = "auto" ] && BACKUP_RUN_GIVEN=""

if [ "${BACKUP_COMMAND}" = "help" ] && [ -z "${BACKUP_SOURCE_ONLY:-}" ]; then
  backup_help help
  exit 0
fi
BACKUP_REFUSED=""
[ -n "${BACKUP_REJECT}" ] && BACKUP_REFUSED="unknown option [${BACKUP_REJECT}]"
case "${BACKUP_COMMAND}" in
start | stop | tail | list | auto | help) ;;
*) BACKUP_REFUSED="unknown command [${BACKUP_COMMAND}]" ;;
esac
case "${BACKUP_STAGE}" in
all | primary | secondary | tertiary) ;;
*) BACKUP_REFUSED="unknown stage [${BACKUP_STAGE}]" ;;
esac
if [ "${BACKUP_SCRUB_ASKED}" -eq 1 ]; then
  case "${BACKUP_STAGE}" in
  all | tertiary) ;;
  *) BACKUP_REFUSED="only tertiary scrubs, not stage [${BACKUP_STAGE}]" ;;
  esac
fi
if [ -n "${BACKUP_REFUSED}" ]; then
  [ -z "${BACKUP_SOURCE_ONLY:-}" ] || return 0 2>/dev/null || true
  backup_log ERROR "${BACKUP_REFUSED}"
  backup_help
  exit 2
fi

BACKUP_TRIGGER="${BACKUP_TRIGGER:-manual}"
[ -n "${BACKUP_RUN_ID_PASSED:-}" ] && BACKUP_TRIGGER="scheduled"
if [ -z "${BACKUP_SCRUB}" ]; then
  BACKUP_SCRUB=0
  BACKUP_SCRUB_TODAY="$(date +%-d)"
  [ "${BACKUP_TRIGGER}" = "scheduled" ] && [ "${BACKUP_SCRUB_TODAY}" -ge "${BACKUP_SCRUB_DAY}" ] &&
    [ "${BACKUP_SCRUB_TODAY}" -lt $(( BACKUP_SCRUB_DAY + BACKUP_SCRUB_WINDOW )) ] && BACKUP_SCRUB=1
fi
export BACKUP_SCRUB BACKUP_SCRUB_FORCED
BACKUP_STATE_RUNNING="running"
BACKUP_STATE_COMPLETE="complete"
BACKUP_STATE_SKIPPED="skipped"
BACKUP_STATE_STOPPED="stopped"
BACKUP_STATE_TIMEDOUT="timedout"
BACKUP_STATE_HALTED="halted"
BACKUP_STATE_FAILED="failed"
BACKUP_STATE_FINISHED="finished"
BACKUP_STATE_INTERRUPTED="interrupted"
BACKUP_COMMAND_ON="ON"
BACKUP_COMMAND_OFF="OFF"
BACKUP_RUNNING_MATCH='"state": "'"${BACKUP_STATE_RUNNING}"'"'
BACKUP_REAPER_TOPIC="supervisor/cluster-all/backup/reaper"
BACKUP_SCHEDULED_HOUR=1
BACKUP_BAR_WIDTH=18
BACKUP_RATE_POINTS="${BACKUP_RATE_POINTS:-12}"
BACKUP_RATE_QUANTUM="${BACKUP_RATE_QUANTUM:-104857600}"
BACKUP_REAP_WAIT="${BACKUP_REAP_WAIT:-15}"
BACKUP_TAIL_PROGRESS="${BACKUP_TAIL_PROGRESS:-10}"
BACKUP_TAIL_POLL="${BACKUP_TAIL_POLL:-2}"
BACKUP_TAIL_STALE="${BACKUP_TAIL_STALE:-300}"
BACKUP_TAIL_STALL="${BACKUP_TAIL_STALL:-300}"
BACKUP_STOP_SECONDS="${BACKUP_STOP_SECONDS:-300}"
BACKUP_LIST_WIDTHS=(19 19 9 9 9 9 9 9 13 9 8 25 10)
BACKUP_LIST_RIGHTS=(2 8 9 10 11)
BACKUP_LIST_RUNS=()
BACKUP_FSTAB="${BACKUP_FSTAB:-/etc/fstab}"
BACKUP_INSTALL_ROOT="${BACKUP_INSTALL_ROOT:-/var/lib/asystem/install}"
BACKUP_HOME_ROOT="${BACKUP_HOME_ROOT:-/home/asystem}"
if [ -z "${BACKUP_RUN_GIVEN}" ] && [ -z "${BACKUP_RUN_ID:-}" ] && [ "${BACKUP_COMMAND}" = "stop" ]; then
  BACKUP_RUN_ID="$(grep -l "${BACKUP_RUNNING_MATCH}" "${BACKUP_HOME_ROOT}"/supervisor/backup/*/stage/*/status.json 2>/dev/null |
    awk -F/ '{ print $(NF-3) }' | sort | tail -1)"
  [ -n "${BACKUP_RUN_ID}" ] ||
    BACKUP_RUN_ID="$(find "${BACKUP_HOME_ROOT}/supervisor/backup" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -1)"
fi
BACKUP_RUN_ID="${BACKUP_RUN_GIVEN:-${BACKUP_RUN_ID:-$(date +%Y-%m-%d_%H-%M-%S)}}"
BACKUP_RUN_PATH="${BACKUP_RUN_PATH:-${BACKUP_HOME_ROOT}/supervisor/backup/${BACKUP_RUN_ID}}"
BACKUP_STAGE_DIR="${BACKUP_RUN_PATH}/stage/${BACKUP_STAGE}"
BACKUP_SERVICE_PATH="${BACKUP_RUN_PATH}/stage/primary/service"
BACKUP_LOG="${BACKUP_STAGE_DIR}/output.log"
BACKUP_LOCK="$(dirname "${BACKUP_RUN_PATH}")/.lock"
BACKUP_CONFIG="${BACKUP_INSTALL_ROOT}/supervisor/latest/image/config.json"
BACKUP_STALL_AT=0
BACKUP_STALL_MARK=""
BACKUP_STALL_WARNED=0
BACKUP_STOPPING="${BACKUP_STOPPING:-}"
BACKUP_SEEN_STAGES=""
BACKUP_DONE_STAGES=""

backup_epoch() {
  local run="$1" stamp clock
  stamp="${run%%_*}"
  clock="${run#*_}"
  date -d "${stamp} ${clock//-/:}" +%s 2>/dev/null || date +%s
}

backup_elapsed() {
  local seconds="$1"
  printf '%02dh%02dm%02ds' $(( seconds / 3600 )) $(( seconds % 3600 / 60 )) $(( seconds % 60 ))
}

# shellcheck disable=SC2329
backup_interrupt() {
  echo >&2
  backup_log WARN "tail stopped, run [${BACKUP_RUN_ID}] continues in the background"
  backup_log WARN "follow it again with [${0} tail] or end it with [${0} stop]"
  exit 0
}

backup_tail() {
  local base run path sequence="${2:-}" expected="${3:-}"
  base="$(dirname "${BACKUP_RUN_PATH}")"
  run="${1:-}"
  [ -n "${run}" ] || run="$(find "${base}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -1)"
  [ -n "${run}" ] || { backup_log ERROR "no backup run found under [${base}]"; return 1; }
  path="${base}/${run}"
  while [ -n "${sequence}" ] && [ ! -d "${path}" ] && kill -0 "${sequence}" 2>/dev/null; do sleep 1; done
  [ -d "${path}" ] || { backup_log ERROR "no backup run at [${path}]"; return 1; }
  [ "${BACKUP_COMMAND}" = "tail" ] && backup_log INFO "following run [${run}] under [${path}]"
  trap 'backup_interrupt' INT
  backup_await "${path}" "" "${sequence}"
  trap - INT
  backup_status "${path}" "${expected}"
}

backup_resulted() {
  local ran="$1" halted="$2" broke="$3"
  [ "${broke}" -gt 0 ] && { printf '%s' "${BACKUP_STATE_FAILED}"; return 0; }
  [ "${halted}" -gt 0 ] && { printf '%s' "${BACKUP_STATE_HALTED}"; return 0; }
  [ "${ran}" -gt 0 ] && { printf '%s' "${BACKUP_STATE_COMPLETE}"; return 0; }
  printf '%s' "-"
}

backup_result() {
  local doc="$1" state
  [ -f "${doc}" ] || { printf '%s' "-"; return 0; }
  state="$(backup_tail_field "${doc}" state)"
  [ "${state}" = "${BACKUP_STATE_RUNNING}" ] && { printf '%s' "${BACKUP_STATE_RUNNING}"; return 0; }
  case "${state}" in "${BACKUP_STATE_STOPPED}" | "${BACKUP_STATE_TIMEDOUT}") printf '%s' "${state}"; return 0 ;; esac
  [ "$(backup_tail_field "${doc}" success_bool)" = "true" ] && { printf '%s' "success"; return 0; }
  printf '%s' "${state:-unknown}"
}

backup_bar() {
  local percent="${1:-}" filled
  case "${percent}" in '' | *[!0-9]*) printf '%s' "-"; return 0 ;; esac
  [ "${percent}" -le 100 ] || percent=100
  filled=$(( percent * BACKUP_BAR_WIDTH / 100 ))
  printf '[%s%s] %3s%%' \
    "$(printf '%*s' "${filled}" '' | tr ' ' '#')" \
    "$(printf '%*s' $(( BACKUP_BAR_WIDTH - filled )) '' | tr ' ' '.')" \
    "${percent}"
}

backup_megabytes() {
  local megabytes="${1:-}" grouped="" rest
  [ "${megabytes}" -ge 0 ] 2>/dev/null || { printf '%s' "-"; return 0; }
  rest="${megabytes}"
  while [ "${#rest}" -gt 3 ]; do
    grouped=",${rest: -3}${grouped}"
    rest="${rest:0:${#rest} - 3}"
  done
  printf '%s MB' "${rest}${grouped}"
}

backup_rated() {
  local megabytes="${1:-0}" seconds="${2:-0}"
  { [ "${seconds}" -gt 0 ] && [ "${megabytes}" -ge 0 ]; } 2>/dev/null || { backup_throughput "-"; return 0; }
  backup_throughput $(( megabytes / seconds ))
}

backup_terabytes() {
  local megabytes="${1:-}" tenths
  case "${megabytes}" in '' | *[!0-9]*) printf '%s' "-"; return 0 ;; esac
  tenths=$(( (megabytes + 50000) / 100000 ))
  printf '%d.%d TB' $(( tenths / 10 )) $(( tenths % 10 ))
}

backup_rule() {
  local joined="$1" width out="" first=1
  for width in "${BACKUP_LIST_WIDTHS[@]}"; do
    [ "${first}" -eq 1 ] || out="${out}${joined}"
    first=0
    out="${out}$(printf '%*s' $(( width + 2 )) '' | tr ' ' '-')"
  done
  printf '+%s+\n' "${out}"
}

backup_row() {
  local index=0 out="" value right column
  for value in "$@"; do
    right=""
    for column in "${BACKUP_LIST_RIGHTS[@]}"; do
      [ "${column}" -eq "${index}" ] && right="1" && break
    done
    if [ -n "${right}" ]; then
      out="${out}$(printf ' %*s ' "${BACKUP_LIST_WIDTHS[index]}" "${value}")|"
    else
      out="${out}$(printf ' %-*s ' "${BACKUP_LIST_WIDTHS[index]}" "${value}")|"
    fi
    index=$(( index + 1 ))
  done
  printf '|%s\n' "${out}"
}

backup_reaper() {
  command -v mosquitto_sub >/dev/null 2>&1 || return 1
  [ -n "${BROKER_HOST:-}" ] || return 1
  mosquitto_sub -h "${BROKER_HOST}" -p "${BROKER_PORT:-1883}" \
    ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -t "${BACKUP_REAPER_TOPIC}" -C 1 -W 5 2>/dev/null
}

backup_scheduled() {
  local stamp
  stamp="$(date -d "today ${BACKUP_SCHEDULED_HOUR}:00:00" --iso-8601=seconds 2>/dev/null)"
  [ -n "${stamp}" ] || return 1
  [ "$(date -d "${stamp}" +%s)" -gt "$(date +%s)" ] ||
    stamp="$(date -d "tomorrow ${BACKUP_SCHEDULED_HOUR}:00:00" --iso-8601=seconds 2>/dev/null)"
  printf '%s' "${stamp}"
}

backup_auto() {
  local want="${1:-}" payload held state expires
  if [ -z "${want}" ]; then
    held="$(backup_reaper)"
    state="$(printf '%s' "${held}" | jq -r '.state // empty' 2>/dev/null)"
    expires="$(printf '%s' "${held}" | jq -r '.expires_ts // empty' 2>/dev/null)"
    if [ -z "${held}" ]; then
      backup_log INFO "reaper is undeclared, which the estate reads as armed, pass [on] to state it"
    elif [ "${state}" = "${BACKUP_COMMAND_OFF}" ] && [ -n "${expires}" ]; then
      backup_log INFO "reaper is paused until [${expires}], the backup disk stays powered until then"
    elif [ "${state}" = "${BACKUP_COMMAND_ON}" ]; then
      backup_log INFO "reaper is armed, the backup disk is powered down again when nothing needs it"
    else
      backup_log WARN "reaper reads [${held}], which states no deadline, so the estate reads it as armed"
    fi
    return 0
  fi
  case "${want}" in
  off)
    expires="$(backup_scheduled)" ||
      { backup_log ERROR "could not resolve the next [${BACKUP_SCHEDULED_HOUR}:00] run to pause the reaper until"; return 1; }
    payload="$(printf '{"state":"%s","expires_ts":"%s"}' "${BACKUP_COMMAND_OFF}" "${expires}")"
    ;;
  on)
    expires=""
    payload="$(printf '{"state":"%s","expires_ts":""}' "${BACKUP_COMMAND_ON}")"
    ;;
  *) backup_log ERROR "auto reads [${want}], taking [on] to turn the reaper on or [off] to turn it off"; return 2 ;;
  esac
  if ! backup_publish "${BACKUP_REAPER_TOPIC}" "${payload}"; then
    backup_log ERROR "could not publish [${payload}] to [${BACKUP_REAPER_TOPIC}], is the broker reachable"
    return 1
  fi
  if [ -n "${expires}" ]; then
    backup_log INFO "reaper paused until [${expires}], the backup disk stays powered until then whatever else happens"
  else
    backup_log INFO "reaper armed, the backup disk is powered down again when nothing needs it"
  fi
  return 0
}

backup_list() {
  local base run path stage state doc live cells result began elapsed finished trigger latest ended sized
  local ran halted broke alive
  local size volume held scrub used_disk_mb total_disk_mb scrub_doc
  base="$(dirname "${BACKUP_RUN_PATH}")"
  mapfile -t BACKUP_LIST_RUNS < <(find "${base}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r)
  if [ "${#BACKUP_LIST_RUNS[@]}" -eq 0 ]; then
    backup_log WARN "no backup runs under [${base}]"
    return 1
  fi
  echo
  backup_rule "+"
  backup_row "STARTED (RUN-ID)" FINISHED DURATION TRIGGER PRIMARY SECONDARY TERTIARY SCRUB DELTA SIZE CAPACITY USED RESULT
  backup_rule "+"
  for run in "${BACKUP_LIST_RUNS[@]}"; do
    path="${base}/${run}"
    began="$(backup_epoch "${run}")"
    live=0
    backup_running "${run}" && live=1
    cells=()
    trigger=""
    size=0
    sized=""
    volume="-"
    scrub="-"
    used_disk_mb="-"
    total_disk_mb="-"
    ran=0
    halted=0
    broke=0
    alive=0
    for stage in primary secondary tertiary; do
      doc="${path}/stage/${stage}/status.json"
      state="$(backup_result "${doc}")"
      [ -n "${trigger}" ] || trigger="$(backup_tail_field "${doc}" trigger)"
      case "${state}" in
      -) ;;
      "${BACKUP_STATE_RUNNING}") alive=1 ;;
      success) ran=1 ;;
      "${BACKUP_STATE_STOPPED}" | "${BACKUP_STATE_TIMEDOUT}") halted=1 ;;
      *) broke=1 ;;
      esac
      if [ -f "${doc}" ]; then
        held="$(backup_tail_field "${doc}" size_mb)"
        [ -z "${held}" ] || { size=$(( size + held )); sized=1; }
        if [ "${stage}" = "tertiary" ]; then
          volume="$(backup_tail_field "${doc}" disk_usage_perc)"
          used_disk_mb="$(backup_tail_field "${doc}" disk_used_mb)"
          total_disk_mb="$(backup_tail_field "${doc}" disk_total_mb)"
        fi
      fi
      cells+=("${state}")
    done
    scrub_doc="${path}/stage/tertiary/scrub.json"
    [ -f "${scrub_doc}" ] && scrub="$(backup_tail_field "${scrub_doc}" state)"
    result="$(backup_tail_field "${path}/status.json" state)"
    [ -n "${result}" ] || result="$(backup_resulted "${ran}" "${halted}" "${broke}")"
    { [ "${alive}" -eq 1 ] || [ "${live}" -eq 1 ]; } && result="${BACKUP_STATE_RUNNING}"
    latest=0
    for stage in primary secondary tertiary; do
      ended="$(backup_tail_field "${path}/stage/${stage}/status.json" finished_ts)"
      [ -n "${ended}" ] || continue
      ended="$(date -d "${ended}" +%s 2>/dev/null || echo 0)"
      [ "${ended}" -gt "${latest}" ] && latest="${ended}"
    done
    finished="-"
    if [ "${result}" = "${BACKUP_STATE_RUNNING}" ]; then
      elapsed="$(backup_elapsed $(( $(date +%s) - began )))"
    else
      elapsed="-"
      [ "${latest}" -gt "${began}" ] && elapsed="$(backup_elapsed $(( latest - began )))"
      [ "${latest}" -gt 0 ] && finished="$(date -d @"${latest}" '+%Y-%m-%d_%H-%M-%S' 2>/dev/null || echo "-")"
    fi
    backup_row "${run}" "${finished}" "${elapsed}" "${trigger:--}" "${cells[@]}" "${scrub:--}" \
      "$(backup_megabytes "${sized:+${size}}")" "$(backup_terabytes "${used_disk_mb}")" \
      "$(backup_terabytes "${total_disk_mb}")" "$(backup_bar "${volume}")" "${result}"
  done
  backup_rule "+"
  echo
  return 0
}

backup_sequence() {
  local stage result=0 started sequence stages
  mapfile -t stages < <(backup_stages)
  if [ "${BACKUP_COMMAND}" = "start" ]; then
    backup_announce "${stages[*]}"
  else
    backup_log INFO "stopping run [${BACKUP_RUN_ID}] over [${stages[*]}]"
  fi
  if [ "${BACKUP_COMMAND}" = "stop" ]; then
    local targets=("${BACKUP_RUN_ID}") target
    BACKUP_STOPPING=1
    if [ -z "${BACKUP_RUN_GIVEN}" ]; then
      mapfile -t targets < <(backup_actives)
      if [ "${#targets[@]}" -eq 0 ]; then
        targets=("${BACKUP_RUN_ID}")
        backup_stopping "no active run, sweeping run [${targets[0]}] for leftovers"
      else
        backup_stopping "stopping [${#targets[@]}] active run(s) [${targets[*]}]"
      fi
    fi
    local base; base="$(dirname "${BACKUP_RUN_PATH}")"
    BACKUP_RUN_ID="${targets[-1]}"
    BACKUP_RUN_PATH="${base}/${BACKUP_RUN_ID}"
    for target in "${targets[@]}"; do
      for stage in "${stages[@]}"; do
        BACKUP_DETACHED=1 BACKUP_STOP_SECONDS=0 BACKUP_STOP_FORCED=1 \
          BACKUP_STOPPING=1 "$0" stop "${target}" --stage "${stage}" || result=$?
      done
    done
    for target in "${targets[@]}"; do
      backup_await "${base}/${target}" "${BACKUP_STOP_SECONDS}" ||
        backup_log WARN "run [${target}] is still running after [${BACKUP_STOP_SECONDS}] s"
      backup_status "${base}/${target}" || result=1
    done
    return "${result}"
  fi
  started="$(date +%s)"
  set -m
  (
    local staged=0
    for stage in "${stages[@]}"; do
      BACKUP_DETACHED=1 "$0" start "${BACKUP_RUN_ID}" --stage "${stage}" || { staged=1; break; }
    done
    backup_rollup "${started}"
    exit "${staged}"
  ) &
  sequence=$!
  set +m
  backup_tail "${BACKUP_RUN_ID}" "${sequence}" "${stages[*]}" || result=1
  wait "${sequence}" || result=1
  return "${result}"
}

backup_rollup() {
  local started="$1" stage doc run=0 failed=0 partial=0 state success=true
  for stage in primary secondary tertiary; do
    doc="${BACKUP_RUN_PATH}/stage/${stage}/status.json"
    [ -f "${doc}" ] || continue
    run=$(( run + 1 ))
    [ "$(backup_tail_field "${doc}" success_bool)" = "true" ] && continue
    case "$(backup_result "${doc}")" in
    "${BACKUP_STATE_STOPPED}" | "${BACKUP_STATE_TIMEDOUT}") partial=$(( partial + 1 )) ;;
    *) failed=$(( failed + 1 )) ;;
    esac
  done
  [ "${run}" -gt 0 ] || return 0
  if [ "${failed}" -gt 0 ] || [ "${partial}" -gt 0 ]; then success=false; fi
  state="$(backup_resulted "${run}" "${partial}" "${failed}")"
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
  "stages_failed": ${failed},
  "stages_halted": ${partial}
}
JSON
  mv "${BACKUP_RUN_PATH}/status.json.tmp" "${BACKUP_RUN_PATH}/status.json"
}

backup_running() {
  local run="$1" pid
  while read -r pid; do
    [ -n "${pid}" ] || continue
    [ "${pid}" = "$$" ] && continue
    return 0
  done < <(pgrep -f "backup\.sh (start|stop) ${run} --stage (primary|secondary|tertiary)" 2>/dev/null)
  return 1
}

backup_await() {
  local path="$1" stage doc deadline=0 sequence="${3:-}" started now due stamped
  started="$(date +%s)"
  due=$(( started + BACKUP_TAIL_PROGRESS ))
  [ -n "${2:-}" ] && deadline=$(( started + $2 ))
  while :; do
    sleep "${BACKUP_TAIL_POLL}"
    now="$(date +%s)"
    if [ "${deadline}" -eq 0 ]; then
      for stage in primary secondary tertiary; do
        doc="${path}/stage/${stage}/status.json"
        [ -f "${doc}" ] || continue
        case " ${BACKUP_SEEN_STAGES} " in
        *" ${stage} "*) ;;
        *)
          BACKUP_SEEN_STAGES="${BACKUP_SEEN_STAGES} ${stage}"
          backup_started "${stage}" "${doc}"
          [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] &&
            backup_progress "${path}" "${stage}"
          ;;
        esac
        [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] && continue
        case " ${BACKUP_DONE_STAGES} " in *" ${stage} "*) continue ;; esac
        BACKUP_DONE_STAGES="${BACKUP_DONE_STAGES} ${stage}"
        [ "${stage}" = "tertiary" ] || backup_progress "${path}" "${stage}"
        backup_finished "${stage}" "${doc}"
      done
    fi
    if [ "${BACKUP_TAIL_PROGRESS}" -gt 0 ] && [ "${now}" -ge "${due}" ]; then
      if [ "${deadline}" -eq 0 ]; then
        backup_progress "${path}"
      else
        backup_stopping "waiting for run [$(basename "${path}")] to finish stopping"
      fi
      due=$(( now + BACKUP_TAIL_PROGRESS ))
    fi
    [ "${deadline}" -gt 0 ] && [ "${now}" -ge "${deadline}" ] && return 1
    [ -n "${sequence}" ] && kill -0 "${sequence}" 2>/dev/null && continue
    backup_running "$(basename "${path}")" && continue
    for stage in primary secondary tertiary; do
      doc="${path}/stage/${stage}/status.json"
      [ -f "${doc}" ] || continue
      [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] || continue
      stamped="$(stat -c %Y "${doc}" 2>/dev/null || echo 0)"
      [ $(( now - stamped )) -lt "${BACKUP_TAIL_STALE}" ] && continue 2
    done
    return 0
  done
}

backup_stalled() {
  local active="$1" now="$2" moved="$3" used="$4" silent="${BACKUP_TAIL_STALL}" mark
  mark="${used:-}"
  [ -n "${mark}" ] || mark="${moved}"
  [ "${BACKUP_STALL_AT}" -eq 0 ] && BACKUP_STALL_AT="${now}"
  if [ "${mark}" != "${BACKUP_STALL_MARK}" ]; then
    BACKUP_STALL_MARK="${mark}"
    BACKUP_STALL_AT="${now}"
    if [ "${BACKUP_STALL_WARNED}" -eq 1 ]; then
      BACKUP_STALL_WARNED=0
      backup_log INFO "progress resumed from [${active:-none}]"
    fi
    return 0
  fi
  [ "${BACKUP_STALL_WARNED}" -eq 1 ] && return 0
  [ $(( now - BACKUP_STALL_AT )) -ge "${silent}" ] || return 0
  BACKUP_STALL_WARNED=1
  backup_log WARN "no bytes copied by [${active:-none}] in [$(( now - BACKUP_STALL_AT ))] s"
}

backup_active() {
  backup_actives | tail -1
}

backup_actives() {
  local doc now stamped
  now="$(date +%s)"
  {
    grep -l "${BACKUP_RUNNING_MATCH}" "${BACKUP_HOME_ROOT}"/supervisor/backup/*/stage/*/status.json 2>/dev/null |
      while read -r doc; do
        stamped="$(stat -c %Y "${doc}" 2>/dev/null || echo 0)"
        [ $(( now - stamped )) -lt "${BACKUP_TAIL_STALE}" ] || continue
        printf '%s\n' "${doc}"
      done |
      awk -F/ '{ print $(NF-3) }'
    pgrep -af "backup\.sh start [^ ]+ --stage (primary|secondary|tertiary)" 2>/dev/null |
      awk '{ for (i = 1; i < NF; i++) if ($i == "start") { print $(i + 1); break } }' |
      while read -r doc; do
        [ -d "${BACKUP_HOME_ROOT}/supervisor/backup/${doc}" ] && printf '%s\n' "${doc}"
      done
  } | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}_' | sort -u
  return 0
}

backup_previous() {
  local stage="$1" field="$2" want="${3-${BACKUP_STATE_COMPLETE}}" doc value state
  while read -r doc; do
    [ -f "${doc}" ] || continue
    state="$(backup_tail_field "${doc}" state)"
    [ "${state}" = "${BACKUP_STATE_RUNNING}" ] && continue
    [ -z "${want}" ] || [ "${state}" = "${want}" ] || continue
    value="$(backup_tail_field "${doc}" "${field}")"
    [ -n "${value}" ] || continue
    printf '%s' "${value}"
    return 0
  done < <(find "$(dirname "${BACKUP_RUN_PATH}")" -mindepth 4 -maxdepth 4 -path "*/stage/${stage}/status.json" -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
  printf '%s' "0"
}

backup_expected() {
  local share sources=0 remaining
  while read -r share; do sources=$(( sources + $(backup_used "${share}") )); done < <(backup_mounted)
  if backup_verified /backup; then
    remaining=$(( sources - $(backup_used /backup) ))
    [ "${remaining}" -gt $(( sources / 100 )) ] && { printf '%s' "${remaining}"; return 0; }
  elif [ "$(backup_previous tertiary duration_s)" -le 0 ] 2>/dev/null; then
    printf '%s' "${sources}"
    return 0
  fi
  printf '%s' "$(( $(backup_previous tertiary size_mb) * 1048576 ))"
}

backup_flushing() {
  local dirty writeback rate megabytes
  dirty="$(awk '/^Dirty:/ { print $2 }' /proc/meminfo 2>/dev/null)"
  writeback="$(awk '/^Writeback:/ { print $2 }' /proc/meminfo 2>/dev/null)"
  megabytes=$(( ( ${dirty:-0} + ${writeback:-0} ) / 1024 ))
  rate="${BACKUP_FLUSH_RATE_MB:-20}"
  [ "${rate}" -gt 0 ] 2>/dev/null || rate=20
  printf '%s %s' "${megabytes}" "$(( megabytes / rate ))"
}

backup_marker() {
  local stage="$1"; shift
  [ "${stage}" = "all" ] && stage=""
  backup_line INFO "${stage}" "$*"
}

backup_stopping() {
  if [ -z "${BACKUP_STOPPING}" ]; then
    backup_log INFO "$*"
    return 0
  fi
  backup_marker "${BACKUP_STAGE}" "$*"
}

backup_started() {
  local stage="$1" doc="${2:-}" began="" hours="${BACKUP_TIMEOUT_HOURS}" minutes="-" until="unknown"
  if [ -n "${doc}" ]; then
    began="$(backup_tail_field "${doc}" started_ts)"
    hours="$(backup_tail_field "${doc}" timeout_hours)"
  fi
  if [ "${hours:-0}" -gt 0 ] 2>/dev/null; then
    minutes=$(( hours * 60 ))
    until="$(date -d "${began:-now} + ${hours} hours" '+%H:%M:%S' 2>/dev/null || echo unknown)"
  fi
  backup_marker "${stage}" "$(printf 'starting with timeout [%4s] min until [%s]' "${minutes}" "${until:-unknown}")"
}

backup_finished() {
  local stage="$1" doc="$2" status="success" pointer="" spent moved rate
  if [ "$(backup_tail_field "${doc}" success_bool)" != "true" ]; then
    status="$(backup_tail_field "${doc}" state)"
    pointer=", see [$(dirname "${doc}")/output.log]"
  fi
  spent="$(backup_tail_field "${doc}" duration_s)"
  moved="$(backup_tail_field "${doc}" size_mb)"
  rate="$(backup_rated "${moved}" "${spent}")"
  backup_marker "${stage}" "$(printf 'finished with status [%s] in [%s] with size [%s] MB at [%s] MB/s and disk at [%s] percent%s' \
    "${status}" \
    "$(backup_elapsed "${spent}")" \
    "$(backup_sized "${moved}")" \
    "${rate}" \
    "$(backup_percent "$(backup_tail_field "${doc}" disk_usage_perc)")" \
    "${pointer}")"
}

backup_verb() {
  case "$1" in
  primary) printf '%s' "exported" ;;
  secondary) printf '%s' "promoted" ;;
  tertiary) printf '%s' "mirrored" ;;
  *) printf '%s' "captured" ;;
  esac
}

backup_active_stage() {
  local path="$1" forced="${2:-}" stage doc active=""
  [ -n "${forced}" ] && { printf '%s' "${forced}"; return 0; }
  for stage in primary secondary tertiary; do
    doc="${path}/stage/${stage}/status.json"
    [ -f "${doc}" ] || continue
    [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] && active="${stage}"
  done
  if [ -z "${active}" ]; then
    active="$(find "${path}/stage" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %f\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
    [ -n "${active}" ] && [ -f "${path}/stage/${active}/status.json" ] && active=""
  fi
  printf '%s' "${active}"
}

backup_progressed() {
  local verb="$1" copied="$2" total="$3" percent="$4" remaining="$5" eta="$6" rate="$7" last=0 line
  [ "${total}" = "-" ] || last=1
  [ "${rate}" = "-" ] || last=2
  [ "${percent}" = "-" ] || last=3
  [ "${remaining}" = "-" ] || last=4
  line="$(printf '%s [%5s] GB' "${verb}" "${copied}")"
  [ "${last}" -ge 1 ] && line="${line}$(printf ' of [%5s] GB' "${total}")"
  [ "${last}" -ge 2 ] && line="${line}$(printf ' at [%s] MB/s' "$(backup_throughput "${rate}")")"
  [ "${last}" -ge 3 ] && line="${line}$(printf ' at [%s] percent complete' "$(backup_percent "${percent}")")"
  [ "${last}" -ge 4 ] &&
    line="${line}$(printf ' and estimated to complete in [%4s] min at [%8s]' "${remaining}" "${eta}")"
  printf '%s' "${line}"
}

backup_eta() {
  local now="$1" remaining="$2"
  case "${remaining}" in '' | *[!0-9]*) printf '%s' "--:--:--"; return 0 ;; esac
  date -d @$(( now + remaining * 60 )) '+%H:%M:%S' 2>/dev/null || printf '%s' "--:--:--"
}

backup_scrubbing() {
  local scrub="$1" now="$2" record="${3:-}" done_mb expires deadline copied total percent rate remaining windowed
  done_mb="$(backup_tail_field "${scrub}" scrubbed_mb)"
  expires="$(backup_tail_field "${scrub}" expires_ts)"
  copied=$(( ${done_mb:-0} / 1024 ))
  total="${copied}"
  backup_verified /backup && total=$(( $(backup_used /backup) / 1073741824 ))
  percent=100
  [ "${total}" -gt 0 ] && percent=$(( copied * 100 / total ))
  [ "${percent}" -le 100 ] || percent=100
  rate="-"
  windowed="$(backup_sampled "$(dirname "${scrub}")/scrub-samples" "$(( ${done_mb:-0} * 1048576 ))" "${record}")" &&
    [ "${windowed:-0}" -gt 0 ] 2>/dev/null && rate="${windowed}"
  remaining="-"
  if [ "${rate}" != "-" ]; then
    remaining=0
    [ "${total}" -gt "${copied}" ] && remaining=$(( (total - copied) * 1024 / rate / 60 ))
  fi
  if [ -n "${expires}" ]; then
    deadline=$(( ( $(date -d "${expires}" +%s 2>/dev/null || echo "${now}") - now ) / 60 ))
    [ "${deadline}" -lt 0 ] && deadline=0
    { [ "${remaining}" = "-" ] || [ "${deadline}" -lt "${remaining}" ]; } && remaining="${deadline}"
  fi
  backup_progressed scrubbed "${copied}" "${total}" "${percent}" "${remaining}" "$(backup_eta "${now}" "${remaining}")" "${rate}"
}

backup_sampled() {
  local file="$1" raw="$2" record="$3" previous points from_stamp from_bytes to_stamp to_bytes span delta
  if [ -n "${record}" ]; then
    previous="$(tail -1 "${file}" 2>/dev/null | cut -d' ' -f2)"
    [ "${previous:-x}" -ge 0 ] 2>/dev/null || previous=""
    if [ -z "${previous}" ] || [ "${raw}" -lt "${previous}" ]; then
      printf '%s %s\n' "$(date +%s)" "${raw}" >"${file}"
    elif [ $(( raw - previous )) -ge "${BACKUP_RATE_QUANTUM}" ]; then
      printf '%s %s\n' "$(date +%s)" "${raw}" >>"${file}"
      tail -n "${BACKUP_RATE_POINTS}" "${file}" >"${file}.tmp" 2>/dev/null &&
        mv "${file}.tmp" "${file}" 2>/dev/null || true
    fi
  fi
  [ -s "${file}" ] || return 1
  points="$(wc -l <"${file}")"
  [ "${points:-0}" -ge 3 ] 2>/dev/null || return 1
  read -r from_stamp from_bytes < <(sed -n 2p "${file}")
  read -r to_stamp to_bytes < <(tail -1 "${file}")
  span=$(( ${to_stamp:-0} - ${from_stamp:-0} ))
  delta=$(( ${to_bytes:-0} - ${from_bytes:-0} ))
  [ "${span}" -gt 0 ] && [ "${delta}" -gt 0 ] || return 1
  printf '%s' $(( delta / 1048576 / span ))
}

backup_mirroring() {
  local path="$1" record="${2:-}" doc began transferred raw used sum copied total percent remaining rate windowed clamped=""
  doc="${path}/stage/tertiary/status.json"
  raw="$(backup_used /backup)"
  began="$(cat "${path}/stage/tertiary/disk-start" 2>/dev/null)"
  transferred=$(( $(backup_tail_field "${doc}" size_mb || echo 0) * 1048576 ))
  sum=$(( $(backup_tail_field "${doc}" total_mb || echo 0) * 1048576 ))
  used=$(( raw - ${began:-0} ))
  [ "${used}" -lt "${transferred}" ] && used="${transferred}"
  [ "${used}" -lt 0 ] && used=0
  [ "${sum}" -lt "${used}" ] && { sum="${used}"; clamped=1; }
  rate="-"
  remaining="-"
  windowed="$(backup_sampled "${path}/stage/tertiary/samples" "${raw}" "${record}")" &&
    [ "${windowed:-0}" -gt 0 ] 2>/dev/null && rate="${windowed}"
  copied=$(( used / 1073741824 ))
  total=$(( sum / 1073741824 ))
  percent="-"
  [ "${sum}" -gt 0 ] && percent=$(( used * 100 / sum ))
  [ "${percent}" = "-" ] || [ "${percent}" -le 100 ] || percent=100
  if [ "${rate}" != "-" ]; then
    remaining=$(( (sum - used) / 1048576 / rate / 60 ))
    [ "${remaining}" -lt 0 ] && remaining=0
  fi
  if [ -n "${clamped}" ]; then
    total="-"
    percent="-"
    remaining="-"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s' "${copied}" "${total}" "${percent}" "${remaining}" "${rate}" "${used}"
}

backup_promoting() {
  local doc="$1" moved whole spent copied total percent remaining rate="-"
  copied="-"; total="-"; percent="-"; remaining="-"
  if [ -f "${doc}" ]; then
    moved="$(backup_tail_field "${doc}" size_mb)"
    whole="$(backup_tail_field "${doc}" total_mb)"
    spent="$(backup_tail_field "${doc}" duration_s)"
    [ "${spent:-0}" -gt 0 ] 2>/dev/null && [ "${moved:-0}" -gt 0 ] 2>/dev/null && rate=$(( moved / spent ))
    copied=$(( ${moved:-0} / 1024 ))
    total=$(( ${whole:-0} / 1024 ))
    [ "${whole:-0}" -gt 0 ] 2>/dev/null && percent=$(( ${moved:-0} * 100 / whole ))
    [ "${rate}" -gt 0 ] 2>/dev/null && remaining=$(( (${whole:-0} - ${moved:-0}) / rate / 60 ))
    [ "${remaining}" = "-" ] || [ "${remaining}" -ge 0 ] || remaining=0
    [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] || remaining=0
  fi
  printf '%s\t%s\t%s\t%s\t%s\t' "${copied}" "${total}" "${percent}" "${remaining}" "${rate}"
}

backup_progress() {
  local path="$1" forced="${2:-}" record="${3:-}" active now scrub copied total percent remaining rate used
  active="$(backup_active_stage "${path}" "${forced}")"
  now="$(date +%s)"
  scrub="${path}/stage/${active}/scrub.json"
  if [ -n "${active}" ] && [ -f "${scrub}" ] && [ "$(backup_tail_field "${scrub}" state)" = "${BACKUP_STATE_RUNNING}" ]; then
    backup_marker "${active}" "$(backup_scrubbing "${scrub}" "${now}" "${record}")"
    return 0
  fi
  if [ "${active}" = "tertiary" ] && backup_verified /backup &&
    [ -f "${path}/stage/tertiary/disk-start" ]; then
    IFS=$'\t' read -r copied total percent remaining rate used < <(backup_mirroring "${path}" "${record}")
  else
    IFS=$'\t' read -r copied total percent remaining rate used < <(backup_promoting "${path}/stage/${active}/status.json")
  fi
  backup_stalled "${active}" "${now}" "${copied}" "${used:-}"
  [ -n "${used:-}" ] && [ "${used}" -lt "${BACKUP_RATE_QUANTUM}" ] 2>/dev/null && return 0
  { [ "${copied}" = "0" ] || [ "${copied}" = "-" ]; } &&
    { [ "${total}" = "0" ] || [ "${total}" = "-" ]; } && return 0
  backup_marker "${active:-none}" "$(backup_progressed "$(backup_verb "${active}")" "${copied}" "${total}" \
    "${percent}" "${remaining}" "$(backup_eta "${now}" "${remaining}")" "${rate}")"
}

backup_status() {
  local path="$1" expected="${2:-}" stage doc faults=0
  if [ -z "${expected}" ]; then
    for stage in primary secondary tertiary; do
      [ -d "${path}/stage/${stage}" ] && expected="${expected}${expected:+ }${stage}"
    done
  fi
  [ -n "${expected}" ] || expected="$(backup_stages | xargs)"
  for stage in ${expected}; do
    doc="${path}/stage/${stage}/status.json"
    if [ ! -f "${doc}" ]; then
      backup_marker "${stage}" "never started"
      continue
    fi
    [ "$(backup_tail_field "${doc}" success_bool)" = "true" ] || faults=$(( faults + 1 ))
  done
  [ "${faults}" -eq 0 ] || return 1
  return 0
}

backup_tail_field() {
  jq -r --arg field "${2}" '.[$field] // empty' "${1}" 2>/dev/null
}


if [ "${BACKUP_COMMAND}" = "stop" ] && [ ! -d "${BACKUP_RUN_PATH}" ]; then
  backup_log ERROR "no backup run at [${BACKUP_RUN_PATH}], refusing to stop"
  exit 2
fi
case "${BACKUP_COMMAND}/${BACKUP_STAGE}" in tail/* | list/* | auto/* | */all) ;; *) mkdir -p "${BACKUP_STAGE_DIR}" ;; esac

BACKUP_ENV="${BACKUP_INSTALL_ROOT}/supervisor/latest/.env"
# shellcheck disable=SC1090
if [ -f "${BACKUP_ENV}" ] && [ -z "${BACKUP_SOURCE_ONLY:-}" ]; then set -a; . "${BACKUP_ENV}"; set +a; fi
BACKUP_HOST="${SUPERVISOR_HOST:-$(hostname)}"

backup_banner() {
  local title="$1"; shift
  backup_log INFO "${title}"
  local field
  for field in "$@"; do backup_log INFO "  ${field}"; done
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

backup_total() {
  local bytes="$1" label="$2" megabytes
  [ "${bytes}" -gt 0 ] 2>/dev/null || bytes=0
  megabytes=$(( bytes / 1048576 ))
  BACKUP_TOTAL="${megabytes}"
  backup_counters
  backup_log INFO "expecting [$(backup_sized "${megabytes}")] MB of [${label}] to transfer"
}

backup_used() {
  local used=""
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "df [$1]" df --output=used -B1 "$1" &&
    used="$(printf '%s\n' "${BACKUP_BOUNDED_OUTPUT}" | tail -1 | tr -d ' ')"
  printf '%s' "${used:-0}"
}

backup_bytes() {
  local sized
  sized="$(du -sb "$1" 2>/dev/null | cut -f1)"
  printf '%s' "${sized:-0}"
}

backup_sized() {
  printf '%4s' "${1:-0}"
}

backup_percent() {
  printf '%2s' "${1:-0}"
}

backup_throughput() {
  printf '%3s' "${1:-0}"
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
  command -v mosquitto_pub >/dev/null 2>&1 || return 1
  [ -n "${BROKER_HOST:-}" ] || return 1
  mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT:-1883}" \
    ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -q 1 -r -t "${topic}" -m "${payload}" 2>/dev/null
}

backup_unclean() {
  local target="$1" kernel="$2"
  dmesg 2>/dev/null | tail -n "+$(( kernel + 1 ))" |
    grep -qiE 'btrfs.*(tree-log replay|has been changed)' || return 0
  backup_log WARN "[${target}] replayed its log at mount, the previous unmount was unclean"
  [ "${target}" = /backup ] || return 0
  printf 'true\n' >"${BACKUP_STAGE_DIR}/disk-unclean" 2>/dev/null || true
}

backup_declared() {
  local target="$1" spec device
  spec="$(awk -v mp="${target}" '$1 !~ /^#/ && $2 == mp { print $1 }' "${BACKUP_FSTAB}")"
  [ -n "${spec}" ] || return 1
  case "${spec}" in
  PARTLABEL=*) device="$(readlink -e "/dev/disk/by-partlabel/${spec#PARTLABEL=}" 2>/dev/null)" ;;
  PARTUUID=*) device="$(readlink -e "/dev/disk/by-partuuid/${spec#PARTUUID=}" 2>/dev/null)" ;;
  UUID=*) device="$(readlink -e "/dev/disk/by-uuid/${spec#UUID=}" 2>/dev/null)" ;;
  LABEL=*) device="$(readlink -e "/dev/disk/by-label/${spec#LABEL=}" 2>/dev/null)" ;;
  //*) device="${spec}" ;;
  /*) device="$(readlink -e "${spec}" 2>/dev/null)" ;;
  *) device="${spec}" ;;
  esac
  [ -n "${device}" ] || return 1
  case "${device}" in /dev/*) [ -b "${device}" ] || return 1 ;; esac
  printf '%s\n' "${device}"
}

backup_sourced() {
  local source
  source="$(findmnt -M "$1" -n -o SOURCE 2>/dev/null | tail -n 1)" || return 1
  [ -n "${source}" ] || return 1
  case "${source}" in
  //*) printf '%s\n' "${source}" ;;
  /*) readlink -e "${source%%\[*}" 2>/dev/null ;;
  *) printf '%s\n' "${source}" ;;
  esac
}

backup_verified() {
  local target="$1" declared current
  declared="$(backup_declared "${target}")" || return 1
  current="$(backup_sourced "${target}")" || return 1
  [ -n "${declared}" ] && [ -n "${current}" ] && [ "${declared}" = "${current}" ]
}

backup_mount() {
  local target="$1" error="" kernel
  backup_verified "${target}" && return 0
  grep -qsE "^[^#][^[:space:]]*[[:space:]]+${target}[[:space:]]" "${BACKUP_FSTAB}" || {
    backup_log ERROR "mount of [${target}] refused, not mounted and not in [${BACKUP_FSTAB}]"
    return 1
  }
  local over=""
  mountpoint -q "${target}" && over=" over [$(backup_sourced "${target}" || echo unknown)]"
  backup_log INFO "mounting [${target}]${over}"
  kernel="$(dmesg 2>/dev/null | wc -l)"
  error="$(mount "${target}" 2>&1)" || ls "${target}" >/dev/null 2>&1 || true
  backup_verified "${target}" && { backup_unclean "${target}" "${kernel}"; return 0; }
  local declared writable=""
  declared="$(backup_declared "${target}" 2>/dev/null)" || declared="unknown"
  case "${declared}" in
  /dev/*) dd if=/dev/null of="${declared}" count=0 2>/dev/null ||
    writable=", device [${declared}] cannot be opened for writing, so a read-write mount can never succeed here" ;;
  esac
  backup_log ERROR "mount of [${target}] failed with [${error:-no reason reported}], [${target}] carries [$(backup_sourced "${target}" || echo nothing)] declared [${declared}]${writable}"
  return 1
}

backup_local() {
  case "$1" in ext4 | xfs | btrfs | f2fs) return 0 ;; *) return 1 ;; esac
}

backup_shares() {
  awk '$1 !~ /^#/ && $2 ~ /^\/share\/[0-9]+$/ { print $2, $3 }' "${BACKUP_FSTAB}" | sort -u
}

backup_mounted() {
  local mount source fstype
  findmnt -rn -o TARGET,SOURCE,FSTYPE 2>/dev/null | while read -r mount source fstype; do
    [[ "${mount}" =~ ^/share/[0-9]+$ ]] || continue
    backup_local "${fstype}" || continue
    case "${source}" in /dev/*) printf '%s\n' "${mount}" ;; esac
  done | sort -u
}

backup_graded() {
  local want="$1" status
  for status in "${BACKUP_SERVICE_PATH}"/*/status.json; do
    [ -f "${status}" ] || continue
    [ "$(jq -r '.success_bool // false' "${status}" 2>/dev/null)" = "${want}" ] &&
      basename "$(dirname "${status}")"
  done
  return 0
}

backup_adopted() {
  local base run
  base="$(dirname "${BACKUP_RUN_PATH}")"
  while read -r run; do
    [ -d "${base}/${run}/stage/primary/service" ] && { echo "${run}"; return 0; }
  done < <(find "${base}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r)
  return 1
}

backup_usage() {
  local uuid="" file allocation used=0 total=0 answered
  case " ${BACKUP_USAGE_WEDGED} " in *" $1 "*) return 0 ;; esac
  case " ${BACKUP_USAGE_UNIDENTIFIED} " in
  *" $1 "*) ;;
  *)
    backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs filesystem show [$1]" btrfs filesystem show "$1"
    answered=$?
    if [ "${answered}" -eq 0 ]; then
      uuid="$(printf '%s\n' "${BACKUP_BOUNDED_OUTPUT}" | sed -n 's/.*uuid: //p' | head -1)"
    elif [ "${answered}" -eq "${BACKUP_BOUNDED_ABANDONED}" ]; then
      BACKUP_USAGE_WEDGED="${BACKUP_USAGE_WEDGED} $1"
      backup_log WARN "holding [$(backup_percent "${BACKUP_USAGE}")] percent as the last usage of [$1], it stopped answering and this stage will not sample it again"
      return 0
    else
      BACKUP_USAGE_UNIDENTIFIED="${BACKUP_USAGE_UNIDENTIFIED} $1"
      backup_log INFO "btrfs could not identify [$1], measuring it with [df] for the rest of this run"
    fi
    ;;
  esac
  if [ -n "${uuid}" ]; then
    for file in "${BACKUP_SYSFS_BTRFS}/${uuid}"/devices/*/size; do
      [ -f "${file}" ] && total=$(( total + $(cat "${file}") * 512 ))
    done
    for allocation in data metadata system; do
      used=$(( used + $(cat "${BACKUP_SYSFS_BTRFS}/${uuid}/allocation/${allocation}/bytes_used" 2>/dev/null || echo 0) ))
    done
  fi
  if [ "${total}" -gt 0 ]; then
    BACKUP_USAGE=$(( used * 100 / total ))
  elif backup_bounded "${BACKUP_BOUNDED_WAIT}" "df [$1]" df --output=used,size -B1 "$1"; then
    read -r used total <<<"$(printf '%s\n' "${BACKUP_BOUNDED_OUTPUT}" | tail -1)"
    used="${used:-0}"
    total="${total:-0}"
    BACKUP_USAGE=0
    [ "${total}" -gt 0 ] && BACKUP_USAGE=$(( used * 100 / total ))
  else
    BACKUP_USAGE_WEDGED="${BACKUP_USAGE_WEDGED} $1"
    backup_log WARN "holding [$(backup_percent "${BACKUP_USAGE}")] percent as the last usage of [$1], neither btrfs nor df answered and this stage will not sample it again"
    return 0
  fi
  printf '%s %s %s\n' "${BACKUP_USAGE}" "$(( used / 1048576 ))" "$(( total / 1048576 ))" \
    >"${BACKUP_STAGE_DIR}/disk-usage.tmp" 2>/dev/null &&
    mv "${BACKUP_STAGE_DIR}/disk-usage.tmp" "${BACKUP_STAGE_DIR}/disk-usage" 2>/dev/null || true
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
  backup_counters
}

backup_partial() {
  local moved
  moved="$(cat "${BACKUP_STAGE_DIR}"/.rsync-*.out 2>/dev/null |
    awk '$3 == "recv" || $3 == "send" { total++ } END { print total + 0 }')"
  [ "${moved:-0}" -gt 0 ] 2>/dev/null || return 0
  BACKUP_FILES=$(( BACKUP_FILES + moved ))
  backup_counters
  backup_log INFO "recovered [${moved}] transferred files from the interrupted rsync, which reported no stats"
}

backup_counted() {
  local began delta
  [ "${BACKUP_STAGE}" = "tertiary" ] || return 0
  [ -f "${BACKUP_STAGE_DIR}/disk-start" ] || return 0
  backup_verified /backup || return 0
  began="$(cat "${BACKUP_STAGE_DIR}/disk-start" 2>/dev/null)"
  delta=$(( ( $(backup_used /backup) - ${began:-0} ) / 1048576 ))
  [ "${delta}" -gt "${BACKUP_SIZE}" ] || return 0
  BACKUP_SIZE="${delta}"
  backup_counters
}

backup_transferred() {
  local verb="$1" what="$2" started="$3"
  backup_count "${BACKUP_RSYNC_OUTPUT}"
  backup_log INFO "${verb} [${what}] in [$(backup_elapsed $(( $(date +%s) - started )))], running total [$(backup_sized "${BACKUP_SIZE}")] MB"
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
    { backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs subvolume delete [${dir}/${name}]" \
      btrfs subvolume delete "${dir}/${name}" || rm -rf "${dir:?}/${name}"; } &&
      backup_log INFO "pruned [${name}] from [${dir}] outside the grandfather father son window"
  done
}

backup_counters() {
  printf '%s %s %s %s %s %s %s %s\n' \
    "${BACKUP_TOTAL}" "${BACKUP_FILES}" "${BACKUP_SIZE}" "${BACKUP_FILES_HELD}" \
    "${BACKUP_FILES_CREATED}" "${BACKUP_FILES_DELETED}" "${BACKUP_SIZE_HELD}" "${BACKUP_SENT}" \
    >"${BACKUP_STAGE_DIR}/counters.tmp" 2>/dev/null &&
    mv "${BACKUP_STAGE_DIR}/counters.tmp" "${BACKUP_STAGE_DIR}/counters" 2>/dev/null || true
}

backup_document() {
  local state="$1" success="$2" started="$3" expires="${4:-}" quiet="${5:-}"
  [ -s "${BACKUP_STAGE_DIR}/counters" ] &&
    read -r BACKUP_TOTAL BACKUP_FILES BACKUP_SIZE BACKUP_FILES_HELD \
      BACKUP_FILES_CREATED BACKUP_FILES_DELETED BACKUP_SIZE_HELD BACKUP_SENT \
      <"${BACKUP_STAGE_DIR}/counters"
  [ -s "${BACKUP_STAGE_DIR}/disk-usage" ] &&
    read -r BACKUP_USAGE BACKUP_USAGE_USED_MB BACKUP_USAGE_TOTAL_MB <"${BACKUP_STAGE_DIR}/disk-usage"
  local unclean=false
  [ -f "${BACKUP_STAGE_DIR}/disk-unclean" ] && unclean=true
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
  "timeout_hours": ${BACKUP_TIMEOUT_HOURS},
  "duration_s": ${duration},
  "success_bool": ${success},
  "disk_usage_perc": ${BACKUP_USAGE:-0},
  "disk_used_mb": ${BACKUP_USAGE_USED_MB:-0},
  "disk_total_mb": ${BACKUP_USAGE_TOTAL_MB:-0},
  "disk_unclean_bool": ${unclean},
  "total_mb": ${BACKUP_TOTAL},
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
  [ -n "${quiet}" ] && return 0
  backup_publish "supervisor/${BACKUP_HOST}/backup/stage/${BACKUP_STAGE}/status" "$(cat "${BACKUP_STAGE_DIR}/status.json")" || true
}

# shellcheck disable=SC2329
backup_interrupted() {
  local state="${BACKUP_STATE_FAILED}"
  [ -f "${BACKUP_STAGE_DIR}/.stopped" ] && state="${BACKUP_STATE_STOPPED}"
  [ -f "${BACKUP_STAGE_DIR}/.timedout" ] && state="${BACKUP_STATE_TIMEDOUT}"
  backup_log WARN "interrupted, [${state}] this stage"
  backup_partial
  backup_counted
  [ "${BACKUP_STAGE}" = "tertiary" ] && backup_verified /backup && backup_usage /backup
  stage_stop || true
  backup_settle
  backup_document "${state}" false "${BACKUP_STARTED}"
  exit 143
}

backup_settle() {
  [ -n "${BACKUP_HEARTBEAT_PID}" ] || return 0
  kill "${BACKUP_HEARTBEAT_PID}" 2>/dev/null
  wait "${BACKUP_HEARTBEAT_PID}" 2>/dev/null
  BACKUP_HEARTBEAT_PID=""
}

backup_heartbeat() {
  local hard=0 nap="" now due tick
  trap '[ -n "${nap}" ] && kill "${nap}" 2>/dev/null; exit 0' TERM
  tick="${BACKUP_TAIL_PROGRESS}"
  [ "${tick}" -gt 0 ] 2>/dev/null || tick=10
  [ "${BACKUP_TIMEOUT_HOURS}" -gt 0 ] 2>/dev/null && hard=$(( BACKUP_STARTED + BACKUP_TIMEOUT_HOURS * 3600 ))
  due=$(( $(date +%s) + BACKUP_HEARTBEAT_REFRESH ))
  while :; do
    sleep "${tick}" &
    nap=$!
    wait "${nap}"
    nap=""
    now="$(date +%s)"
    kill -0 "${BACKUP_MAIN_PID}" 2>/dev/null || return 0
    if [ "${BACKUP_STAGE}" = "tertiary" ] && [ -f "${BACKUP_STAGE_DIR}/disk-device" ] && ! backup_attached; then
      backup_log ERROR "[/backup] is no longer the backup disk, stopping this stage before it writes anywhere else"
      kill -TERM "${BACKUP_MAIN_PID}" 2>/dev/null
      stage_stop || true
      return 0
    fi
    if [ "${hard}" -gt 0 ] && [ "${now}" -ge "${hard}" ]; then
      backup_document "${BACKUP_STATE_RUNNING}" false "${BACKUP_STARTED}" "$(( now - 1 ))"
      backup_log WARN "exceeded the timeout of [${BACKUP_TIMEOUT_HOURS}] hours, stopping this stage, the next run resumes it"
      : >"${BACKUP_STAGE_DIR}/.timedout"
      kill -TERM "${BACKUP_MAIN_PID}" 2>/dev/null
      stage_stop || true
      return 0
    fi
    [ "${BACKUP_STAGE}" = "tertiary" ] && backup_verified /backup && backup_usage /backup
    backup_document "${BACKUP_STATE_RUNNING}" false "${BACKUP_STARTED}" "$(( now + BACKUP_HEARTBEAT_GRACE ))" quiet
    [ "${BACKUP_TAIL_PROGRESS}" -gt 0 ] 2>/dev/null &&
      backup_progress "${BACKUP_RUN_PATH}" "${BACKUP_STAGE}" record
    [ "${now}" -ge "${due}" ] || continue
    due=$(( now + BACKUP_HEARTBEAT_REFRESH ))
    backup_document "${BACKUP_STATE_RUNNING}" false "${BACKUP_STARTED}" "$(( now + BACKUP_HEARTBEAT_GRACE ))"
  done
}

primary_counted() {
  local state="$1" files="$2" size="$3"
  [ "${state}" = "${BACKUP_STATE_COMPLETE}" ] || return 0
  BACKUP_FILES=$(( BACKUP_FILES + files ))
  BACKUP_SIZE=$(( BACKUP_SIZE + size ))
  BACKUP_FILES_CREATED=$(( BACKUP_FILES_CREATED + 1 ))
  backup_counters
}

primary_start() {
  local service script running health failed=0 count=0 index=0 enrolled=() configured=()
  mapfile -t configured < <(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .services[]' "${BACKUP_CONFIG}" 2>/dev/null)
  for service in "${configured[@]}"; do
    [ -x "${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh" ] && enrolled+=("${service}")
  done
  backup_log INFO "configured [${#configured[@]}] services, of which [${#enrolled[@]}] ship a backup.sh"
  backup_total "$(( $(backup_previous primary size_mb) * 1048576 ))" "backup"
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
    backup_marker primary "started [${service}] [${index}/${#enrolled[@]}] with [${script}], logging to [${dir}/output.log]"
    local rc=0
    BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}" BACKUP_SERVICE_RESTART=true BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS}" \
      bash "${script}" >"${dir}/output.log" 2>&1 </dev/null || rc=$?
    local state="${BACKUP_STATE_COMPLETE}" ok=true
    [ "${rc}" -eq 0 ] || { state="${BACKUP_STATE_FAILED}"; ok=false; failed=$(( failed + 1 )); }
    local newest size=0 files=0 kind=unknown version=unknown stamp file stem
    newest="$(find "${BACKUP_HOME_ROOT}/${service}/backup" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | tail -1)"
    [ "${state}" = "${BACKUP_STATE_COMPLETE}" ] && [ "${newest}" = "${previous}" ] && state="${BACKUP_STATE_SKIPPED}"
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
    local spent=$(( $(date +%s) - started )) rated
    rated="$(backup_throughput "-")"
    [ "${state}" = "${BACKUP_STATE_COMPLETE}" ] && rated="$(backup_rated "${size:-0}" "${spent}")"
    backup_marker primary "finished [${service}] as [${state}] in [$(backup_elapsed "${spent}")], kind [${kind}], version [${version}], size [$(backup_sized "${size:-0}")] MB at [${rated}] MB/s"
    primary_counted "${state}" "${files:-0}" "${size:-0}"
    backup_publish "supervisor/${BACKUP_HOST}/backup/stage/primary/service/${service}/status" "$(cat "${dir}/status.json")" || true
  done
  backup_log INFO "attempted [${count}] services with [${failed}] failed"
  backup_usage "${BACKUP_HOME_ROOT}"
  return "${failed}"
}

primary_stop() {
  backup_stopping "terminating any running service backup.sh"
  pkill -CONT -f "${BACKUP_INSTALL_ROOT}/[a-z0-9_-]*/latest/backup.sh" 2>/dev/null || true
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
  mapfile -t promote < <(printf 'supervisor\n'; backup_graded true)
  mapfile -t demoted < <(backup_graded false)
  total="${#promote[@]}"
  for service in "${demoted[@]}"; do
    backup_log WARN "not promoting [${service}], its primary backup did not succeed in run [${adopted:-${BACKUP_RUN_ID}}]"
  done
  if [ "${total}" -eq 1 ]; then
    backup_log WARN "run [${adopted:-${BACKUP_RUN_ID}}] recorded no successful service backup under [${BACKUP_SERVICE_PATH}], promoting [supervisor] alone"
  fi
  local pending=0
  for service in "${promote[@]}"; do
    pending=$(( pending + $(backup_bytes "${BACKUP_HOME_ROOT}/${service}/backup") - $(backup_bytes "$(backup_promotion "${service}" "${share}")") ))
  done
  [ "${pending}" -lt 0 ] && pending=0
  backup_total "${pending}" "promotion"
  backup_log INFO "promoting [${total}] services to [${share}/backup]"
  for service in "${promote[@]}"; do
    promoted=$(( promoted + 1 ))
    local source="${BACKUP_HOME_ROOT}/${service}/backup/"
    local target; target="$(backup_promotion "${service}" "${share}")"
    if [ ! -d "${source}" ]; then
      backup_log WARN "skipped [${service}] [${promoted}/${total}], no backup directory at [${source}]"
      continue
    fi
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -delete 2>/dev/null
    backup_log INFO "promoting [${service}] [${promoted}/${total}] from [${source}] to [${target}]"
    local started; started="$(date +%s)"
    backup_rsync -a --stats --out-format='%t %o %f %l' \
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
  backup_stopping "terminating any running promotion rsync"
  pkill -CONT -f "rsync .*${BACKUP_HOME_ROOT}" 2>/dev/null || true
  pkill -TERM -f "rsync .*${BACKUP_HOME_ROOT}" 2>/dev/null || true
}

backup_attached() {
  local expected
  backup_verified /backup || return 1
  [ -f "${BACKUP_STAGE_DIR}/disk-device" ] || return 0
  expected="$(cat "${BACKUP_STAGE_DIR}/disk-device" 2>/dev/null)"
  [ -n "${expected}" ] || return 0
  [ "$(stat -c %d /backup 2>/dev/null)" = "${expected}" ]
}

backup_promotion() {
  local service="$1" share="$2"
  case "${service}" in
  supervisor) printf '%s/backup/%s/%s' "${share}" "${service}" "${BACKUP_HOST}" ;;
  *) printf '%s/backup/%s' "${share}" "${service}" ;;
  esac
}

backup_ready() {
  local fstype
  backup_verified /backup || return 1
  fstype="$(findmnt -M /backup -n -o FSTYPE 2>/dev/null | tail -n 1)"
  backup_local "${fstype}"
}

backup_targets() {
  awk '$1 !~ /^#/ && ($2 == "/backup" || $2 ~ /^\/backup\//) { print $2 }' "${BACKUP_FSTAB}"
}

backup_stages() {
  local declared
  declared="$(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .stages[]' "${BACKUP_CONFIG}" 2>/dev/null)"
  if [ -z "${declared}" ]; then
    backup_log WARN "[${BACKUP_CONFIG}] declares no backup stages for [${BACKUP_HOST}], assuming [primary secondary]"
    declared="$(printf 'primary\nsecondary')"
  fi
  printf '%s\n' "${declared}"
}

backup_attach() {
  local deadline=$(( $(date +%s) + BACKUP_DISK_SECONDS )) started target pending failed=0
  started="$(date +%s)"
  backup_log INFO "waiting up to [${BACKUP_DISK_SECONDS}] s for [$(backup_targets | xargs)] to enumerate, polling every [${BACKUP_DISK_POLL}] s"
  while :; do
    pending=0
    while read -r target; do
      backup_declared "${target}" >/dev/null || pending=1
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

backup_reaped() {
  local pattern="$1" waited=0
  while pgrep -f "${pattern}" >/dev/null 2>&1; do
    [ "${waited}" -lt "${BACKUP_REAP_WAIT}" ] || {
      backup_log WARN "[${waited}] s on and still holding the disk [${pattern}]"
      return 1
    }
    sleep 1
    waited=$(( waited + 1 ))
  done
  [ "${waited}" -gt 0 ] && backup_log INFO "exited [${pattern}] after [${waited}] s"
  return 0
}

backup_detachable() {
  local target="$1"
  mountpoint -q "${target}" 2>/dev/null || return 1
  backup_verified "${target}" && return 0
  [ "$(stat -c %d "${target}" 2>/dev/null)" != "$(stat -c %d "${BACKUP_HOME_ROOT}" 2>/dev/null)" ]
}

backup_detach() {
  local target
  while read -r target; do
    backup_detachable "${target}" || continue
    backup_bounded "${BACKUP_BOUNDED_WAIT}" "sync [${target}]" sync -f "${target}" || true
    local failure=""
    backup_bounded "${BACKUP_BOUNDED_WAIT}" "umount [${target}]" umount "${target}" || true
    failure="${BACKUP_BOUNDED_OUTPUT}"
    backup_detachable "${target}" || continue
    backup_log WARN "unmount of [${target}] failed with [${failure:-no reason reported}], detaching forcibly and lazily"
    backup_bounded "${BACKUP_BOUNDED_WAIT}" "umount -f -l [${target}]" umount -f -l "${target}" || true
    backup_detachable "${target}" &&
      backup_log WARN "could not detach [${target}], it is still mounted and will need the disk powered back on"
  done < <(backup_targets)
}

backup_scrub_counter() {
  local value
  value="$(printf '%s\n' "$1" | sed -n "s/^[[:space:]]*$2:[[:space:]]*//p" | head -1 | tr -dc '0-9')"
  printf '%s' "${value:-0}"
}

backup_device_counter() {
  printf '%s\n' "$1" | awk -v key="$2" '$1 ~ ("\\]\\." key "$") { total += $2 } END { printf "%d", total + 0 }'
}

backup_balance() {
  local started output relocated
  started="$(date +%s)"
  if ! backup_bounded "${BACKUP_BALANCE_WAIT}" "btrfs balance start [/backup]" \
    btrfs balance start -dusage=10 -musage=10 /backup; then
    output="${BACKUP_BOUNDED_OUTPUT}"
    backup_log WARN "could not balance [/backup] with [${output:-no reason reported}]"
    return 0
  fi
  output="${BACKUP_BOUNDED_OUTPUT}"
  relocated="$(printf '%s\n' "${output}" | sed -n 's/.*relocate \([0-9]*\) out of.*/\1/p' | head -1)"
  BACKUP_RELOCATED="${relocated:-0}"
  backup_log INFO "balanced [${BACKUP_RELOCATED}] chunks relocated on [/backup] in [$(backup_elapsed $(( $(date +%s) - started )))]"
}

backup_scrub_document() {
  local state="$1" success="$2" started="$3" scrubbed="$4" progress="$5" found="$6" corrected="$7" uncorrectable="$8"
  local files="${9:-}" count="${10:-0}" deadline="${11:-0}" expires=""
  [ "${deadline}" -gt 0 ] 2>/dev/null && expires="$(date --iso-8601=seconds -d @"${deadline}")"
  mkdir -p "${BACKUP_STAGE_DIR}"
  cat >"${BACKUP_STAGE_DIR}/scrub.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "state": "${state}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "expires_ts": "${expires}",
  "success_bool": ${success},
  "scrubbed_mb": ${scrubbed},
  "progress_perc": ${progress},
  "errors_found": ${found},
  "errors_corrected": ${corrected},
  "errors_uncorrectable": ${uncorrectable},
  "files_to_delete": "${files}",
  "files_to_delete_count": ${count},
  "device_errors": ${BACKUP_DEVICE_ERRORS},
  "chunks_relocated": ${BACKUP_RELOCATED}
}
JSON
  mv "${BACKUP_STAGE_DIR}/scrub.json.tmp" "${BACKUP_STAGE_DIR}/scrub.json"
  backup_publish "supervisor/${BACKUP_HOST}/backup/stage/tertiary/scrub/status" "$(cat "${BACKUP_STAGE_DIR}/scrub.json")" || true
}

backup_scrub_corrupt() {
  dmesg 2>/dev/null | tail -n "+$(( ${1:-0} + 1 ))" |
    grep -oE '\(path: [^)]+\)' | sed -e 's/^(path: //' -e 's/)$//' | sort -u
}

backup_scrub_reading() {
  local raw status scrubbed progress corrected uncorrectable found phase="${BACKUP_STATE_FINISHED}"
  BACKUP_SCRUB_READING=""
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub status -R [/backup]" btrfs scrub status -R /backup || return 1
  raw="${BACKUP_BOUNDED_OUTPUT}"
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub status [/backup]" btrfs scrub status /backup || return 1
  status="${BACKUP_BOUNDED_OUTPUT}"
  scrubbed=$(( $(backup_scrub_counter "${raw}" "data_bytes_scrubbed") / 1048576 ))
  progress="$(printf '%s\n' "${status}" | sed -n 's/.*(\([0-9.]*\)%).*/\1/p' | head -1)"
  corrected="$(backup_scrub_counter "${raw}" "corrected_errors")"
  uncorrectable="$(backup_scrub_counter "${raw}" "uncorrectable_errors")"
  found=$(( $(backup_scrub_counter "${raw}" "csum_errors") +
    $(backup_scrub_counter "${raw}" "verify_errors") +
    $(backup_scrub_counter "${raw}" "super_errors") ))
  case "${status}" in
  *aborted*) phase=aborted ;;
  *interrupted*) phase="${BACKUP_STATE_INTERRUPTED}" ;;
  *) printf '%s\n' "${raw}" | grep -qi "status:[[:space:]]*running" && phase="${BACKUP_STATE_RUNNING}" ;;
  esac
  BACKUP_SCRUB_READING="$(printf '%s\t%s\t%s\t%s\t%s\t%s' \
    "${scrubbed}" "${progress:-0}" "${found}" "${corrected}" "${uncorrectable}" "${phase}")"
}

backup_scrub_state() {
  case "$1" in
  "${BACKUP_STATE_FINISHED}") printf '%s' "${BACKUP_STATE_FINISHED}" ;;
  *) printf '%s' "${BACKUP_STATE_INTERRUPTED}" ;;
  esac
}

backup_scrub_cancel() {
  command -v btrfs >/dev/null 2>&1 || return 0
  backup_detachable /backup || return 0
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub cancel [/backup]" btrfs scrub cancel /backup || true
  backup_scrub_halted
}

backup_scrub_halted() {
  local doc="${BACKUP_STAGE_DIR}/scrub.json" began scrubbed progress
  [ -f "${doc}" ] || return 0
  [ "$(backup_tail_field "${doc}" state)" = "${BACKUP_STATE_RUNNING}" ] || return 0
  began="$(date -d "$(backup_tail_field "${doc}" started_ts)" +%s 2>/dev/null || date +%s)"
  scrubbed="$(backup_tail_field "${doc}" scrubbed_mb)"
  progress="$(backup_tail_field "${doc}" progress_perc)"
  backup_scrub_document "${BACKUP_STATE_STOPPED}" false "${began}" "${scrubbed:-0}" "${progress:-0}" \
    "$(backup_tail_field "${doc}" errors_found)" "$(backup_tail_field "${doc}" errors_corrected)" \
    "$(backup_tail_field "${doc}" errors_uncorrectable)"
  backup_log WARN "scrub cancelled at [$(backup_percent "${progress:-0}")] percent having scrubbed [$(backup_sized "${scrubbed:-0}")] MB, the next armed run resumes it"
}

backup_scrub() {
  local action started hard since state="${BACKUP_STATE_FINISHED}" success=true phase="${BACKUP_STATE_FINISHED}"
  local scrubbed=0 progress=0 found=0 corrected=0 uncorrectable=0
  local kernel=0 files="" count=0 status devices
  started="$(date +%s)"
  if [ "${BACKUP_SCRUB}" != "1" ]; then
    backup_log INFO "scrub skipped, a [${BACKUP_TRIGGER}] run does not scrub, pass [--scrub] to force one"
    backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
    return 0
  fi
  if ! command -v btrfs >/dev/null 2>&1; then
    backup_log WARN "scrub skipped, no [btrfs] on the PATH"
    backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
    return 0
  fi
  if ! backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs filesystem show [/backup]" btrfs filesystem show /backup; then
    backup_log WARN "scrub skipped, [/backup] did not answer"
    backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
    return 0
  fi
  if ! backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub status [/backup]" btrfs scrub status /backup; then
    backup_log WARN "scrub skipped, [/backup] did not report its scrub status"
    backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
    return 0
  fi
  status="${BACKUP_BOUNDED_OUTPUT}"
  case "${status}" in
  *interrupted* | *aborted*) action="resume" ;;
  *)
    action="start"
    since="$(printf '%s\n' "${status}" | sed -n 's/^Scrub started:[[:space:]]*//p' | head -1)"
    if [ "${BACKUP_SCRUB_FORCED}" != "1" ] && [ -n "${since}" ] &&
      [ "$(date -d "${since}" +%Y-%m 2>/dev/null || echo none)" = "$(date -d @"${started}" +%Y-%m)" ]; then
      backup_log INFO "scrub skipped, the last pass started [${since}] in this month already, pass [--scrub] to force one"
      backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
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
    backup_scrub_document "${BACKUP_STATE_SKIPPED}" true "${started}" 0 0 0 0 0
    return 0
  fi
  kernel="$(dmesg 2>/dev/null | wc -l)"
  backup_log INFO "scrub [${action}] on [/backup] until [$(date --iso-8601=seconds -d @"${hard}")], polling every [${BACKUP_SCRUB_POLL}] s"
  if ! backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub ${action} [/backup]" \
    btrfs scrub "${action}" -c 3 -n 15 /backup; then
    backup_log ERROR "could not [${action}] the scrub on [/backup] with [${BACKUP_BOUNDED_OUTPUT:-no reason reported}]"
    backup_scrub_document "${BACKUP_STATE_FAILED}" false "${started}" 0 0 0 0 0
    return 1
  fi
  local opened="" opened_at gained session
  opened_at="$(date +%s)"
  backup_scrub_reading && IFS=$'\t' read -r opened _ _ _ _ _ <<<"${BACKUP_SCRUB_READING}"
  local silent=0
  while :; do
    sleep "${BACKUP_SCRUB_POLL}"
    if [ "$(date +%s)" -ge "${hard}" ]; then
      backup_log WARN "scrub ran past [$(date --iso-8601=seconds -d @"${hard}")], cancelling it, the next armed run resumes it"
      backup_scrub_cancel
      break
    fi
    if ! backup_scrub_reading; then
      silent=$(( silent + 1 ))
      backup_log WARN "scrub status unanswered [${silent}] of [${BACKUP_SCRUB_SILENCE}] times, the disk may have gone"
      [ "${silent}" -lt "${BACKUP_SCRUB_SILENCE}" ] && continue
      backup_log ERROR "abandoning the scrub, [/backup] has not reported its status [${silent}] times running"
      backup_scrub_cancel
      break
    fi
    silent=0
    IFS=$'\t' read -r scrubbed progress found corrected uncorrectable phase <<<"${BACKUP_SCRUB_READING}"
    backup_log INFO "scrub at [$(backup_percent "${progress}")] percent, scrubbed [$(backup_sized "${scrubbed}")] MB"
    backup_scrub_document "${BACKUP_STATE_RUNNING}" false "${started}" "${scrubbed}" "${progress}" \
      "${found}" "${corrected}" "${uncorrectable}" "" 0 "${hard}"
    [ "${phase}" = "${BACKUP_STATE_RUNNING}" ] || break
  done
  local reached="${progress}"
  if backup_scrub_reading; then
    IFS=$'\t' read -r scrubbed progress found corrected uncorrectable phase <<<"${BACKUP_SCRUB_READING}"
  else
    phase="${BACKUP_STATE_INTERRUPTED}"
  fi
  state="$(backup_scrub_state "${phase}")"
  [ "${progress%%.*}" -eq 0 ] 2>/dev/null && progress="${reached:-0}"
  devices=""
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs device stats [/backup]" btrfs device stats /backup &&
    devices="${BACKUP_BOUNDED_OUTPUT}"
  BACKUP_DEVICE_ERRORS=$(( $(backup_device_counter "${devices}" "write_io_errs") +
    $(backup_device_counter "${devices}" "read_io_errs") +
    $(backup_device_counter "${devices}" "flush_io_errs") +
    $(backup_device_counter "${devices}" "corruption_errs") +
    $(backup_device_counter "${devices}" "generation_errs") ))
  if [ "${found}" -gt 0 ] || [ "${uncorrectable}" -gt 0 ] || [ "${BACKUP_DEVICE_ERRORS}" -gt 0 ]; then
    success=false
    count="$(backup_scrub_corrupt "${kernel}" | wc -l | tr -d ' ')"
    files="$(backup_scrub_corrupt "${kernel}" | head -20 | paste -sd ',' - | sed 's/"/\\"/g')"
    {
      backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs scrub status -R [/backup]" btrfs scrub status -R /backup &&
        printf '%s\n\n' "${BACKUP_BOUNDED_OUTPUT}"
      printf '%s\n\n' "${devices}"
      backup_scrub_corrupt "${kernel}"
      printf '\n'
      dmesg -T 2>/dev/null | tail -n "+$(( kernel + 1 ))" |
        grep -iE 'btrfs.*(csum|checksum|unable to fixup)|usb.*(reset|disconnect)|i/o error|blk_update_request|tag#' | tail -500
    } >"${BACKUP_STAGE_DIR}/scrub.log"
    if [ "${found}" -gt 0 ] || [ "${uncorrectable}" -gt 0 ]; then
      backup_log ERROR "scrub found [${found}] errors with [${uncorrectable}] uncorrectable across [${count}] files and [${BACKUP_DEVICE_ERRORS}] device errors, delete them and re-mirror, listed in [${BACKUP_STAGE_DIR}/scrub.log]"
    else
      backup_log ERROR "scrub found [${BACKUP_DEVICE_ERRORS}] device errors accumulated since the last scrub with no checksum error this pass, counters in [${BACKUP_STAGE_DIR}/scrub.log]"
    fi
  else
    gained=""
    [ -n "${opened}" ] && gained=$(( scrubbed - opened ))
    session="$(backup_rated "${gained:--}" "$(( $(date +%s) - opened_at ))")"
    backup_log INFO "scrub [${state}] at [$(backup_percent "${progress}")] percent having scrubbed [$(backup_sized "${scrubbed}")] MB, [$(backup_sized "${gained:--}")] MB this session at [${session}] MB/s"
  fi
  [ -n "${devices}" ] &&
    { backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs device stats -z [/backup]" btrfs device stats -z /backup || true; }
  { [ "${state}" = "${BACKUP_STATE_FINISHED}" ] && [ "$(date +%s)" -lt "${hard}" ]; } && backup_balance
  backup_scrub_document "${state}" "${success}" "${started}" "${scrubbed}" "${progress}" "${found}" "${corrected}" "${uncorrectable}" "${files}" "${count}"
  [ "${success}" = "true" ]
}

tertiary_start() {
  local share index target failed=0 fstab_target fstab_type command_topic
  command_topic="$(backup_config '.asystem.backup.command_topic' '')"
  if [ -n "${command_topic}" ]; then
    backup_log INFO "powering the backup disk on with [ON] to [${command_topic}]"
    backup_command "${command_topic}" "${BACKUP_COMMAND_ON}" ||
      backup_log WARN "could not publish [ON] to [${command_topic}], the disk must already be powered"
  fi
  if ! backup_attach; then
    backup_log ERROR "backup disk did not come up"
    return 1
  fi
  if ! backup_ready; then
    backup_log ERROR "[/backup] carries [$(backup_sourced /backup || echo nothing)] rather than the declared [$(backup_declared /backup || echo nothing)], refusing to mirror"
    return 1
  fi
  if [ "$(stat -c %d /backup 2>/dev/null)" = "$(stat -c %d "${BACKUP_HOME_ROOT}" 2>/dev/null)" ]; then
    backup_log ERROR "[/backup] shares a filesystem with [${BACKUP_HOME_ROOT}], refusing to mirror onto the host"
    return 1
  fi
  while read -r fstab_target fstab_type; do
    backup_local "${fstab_type}" || continue
    backup_mount "${fstab_target}" || backup_log WARN "could not mount [${fstab_target}]"
  done < <(backup_shares)
  stat -c %d /backup >"${BACKUP_STAGE_DIR}/disk-device" 2>/dev/null
  backup_used /backup >"${BACKUP_STAGE_DIR}/disk-start"
  rm -f "${BACKUP_STAGE_DIR}/samples"
  backup_total "$(backup_expected)" "mirror"
  while read -r share; do
    index="${share#/share/}"
    [[ "${index}" =~ ^[0-9]+$ ]] || continue
    target="/backup/share/${index}"
    mountpoint -q "${share}" || { backup_log ERROR "[${share}] vanished mid-run, skipping"; failed=1; continue; }
    backup_attached || { backup_log ERROR "[/backup] is no longer the backup disk, aborting before writing anywhere else"; failed=1; break; }
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -mtime +7 -delete 2>/dev/null
    backup_log INFO "mirroring [${share}] to [${target}]"
    local started; started="$(date +%s)"
    backup_rsync -a --delete --stats \
      --exclude '/tmp/' --exclude '.rsync/' --exclude '.rsync-*' --exclude '/.lock' \
      --partial-dir="${target}/.rsync" -- "${share}/" "${target}/" || failed=1
    backup_transferred "mirrored" "${share}" "${started}"
  done < <(backup_mounted)
  if backup_verified /backup; then
    if command -v btrfs >/dev/null 2>&1 && backup_ready; then
      local subvolume name snapshots="/backup/.snapshots"
      for subvolume in /backup/share/*; do
        [ -d "${subvolume}" ] || continue
        backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs subvolume show [${subvolume}]" \
          btrfs subvolume show "${subvolume}" || continue
        name="$(basename "${subvolume}")"
        mkdir -p "${snapshots}/share/${name}"
        backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs subvolume snapshot [${subvolume}]" \
          btrfs subvolume snapshot -r "${subvolume}" "${snapshots}/share/${name}/${BACKUP_RUN_ID}" &&
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
  rm -f "${BACKUP_STAGE_DIR}/disk-device"
  backup_stopping "terminating any running mirror and scrub, flushing and unmounting the backup disk"
  backup_scrub_cancel
  command -v btrfs >/dev/null 2>&1 && backup_detachable /backup &&
    { backup_bounded "${BACKUP_BOUNDED_WAIT}" "btrfs balance cancel [/backup]" btrfs balance cancel /backup || true; }
  pkill -CONT -f "rsync .*/backup/share" 2>/dev/null || true
  pkill -TERM -f "rsync .*/backup/share" 2>/dev/null || true
  backup_reaped "rsync .*/backup/share"
  backup_bounded "${BACKUP_BOUNDED_WAIT}" "sync [/backup]" sync -f /backup || true
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
BACKUP_SYSFS_BTRFS="${BACKUP_SYSFS_BTRFS:-/sys/fs/btrfs}"
BACKUP_SCRUB_MARGIN="${BACKUP_SCRUB_MARGIN:-900}"
BACKUP_SCRUB_POLL="${BACKUP_SCRUB_POLL:-30}"
BACKUP_SCRUB_SILENCE="${BACKUP_SCRUB_SILENCE:-3}"
BACKUP_BALANCE_WAIT="${BACKUP_BALANCE_WAIT:-3600}"

BACKUP_USAGE=0
BACKUP_USAGE_USED_MB=0
BACKUP_USAGE_TOTAL_MB=0
BACKUP_DEVICE_ERRORS=0
BACKUP_RELOCATED=0
BACKUP_TOTAL=0
BACKUP_FILES=0
BACKUP_FILES_HELD=0
BACKUP_FILES_CREATED=0
BACKUP_FILES_DELETED=0
BACKUP_SIZE=0
BACKUP_SIZE_HELD=0
BACKUP_SENT=0
BACKUP_RSYNC_OUTPUT=""

# shellcheck disable=SC2317
if [ -n "${BACKUP_SOURCE_ONLY:-}" ]; then return 0 2>/dev/null || exit 0; fi

if [ "${BACKUP_COMMAND}" = "auto" ]; then
  backup_auto "${BACKUP_ARGUMENT}"
  exit $?
fi

if [ "${BACKUP_COMMAND}" = "list" ]; then
  backup_list
  exit $?
fi

if [ "${BACKUP_COMMAND}" = "tail" ]; then
  backup_tail "${BACKUP_RUN_GIVEN}"
  exit $?
fi

if [ "${BACKUP_COMMAND}" = "start" ] && [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && [ -z "${BACKUP_DETACHED:-}" ]; then
  BACKUP_ACTIVE_RUN="$(backup_active)"
  if [ -n "${BACKUP_ACTIVE_RUN}" ] && [ "${BACKUP_ACTIVE_RUN}" != "${BACKUP_RUN_ID}" ]; then
    backup_log ERROR "run [${BACKUP_ACTIVE_RUN}] is already active, refusing to start run [${BACKUP_RUN_ID}]"
    backup_log INFO "watch it with [${0} tail] or stop it with [${0} stop]"
    exit 3
  fi
fi

if [ "${BACKUP_STAGE}" = "all" ]; then
  backup_sequence
  exit $?
fi

if [ "${BACKUP_COMMAND}" = "stop" ]; then
  BACKUP_STOPPING=1
  trap 'backup_log WARN "interrupted, the stop is incomplete and [/backup] may still be mounted"; exit 130' INT TERM
  exec 3>&1
  if [ -n "${BACKUP_RUN_ID_PASSED:-}" ] || [ -n "${BACKUP_QUIET:-}" ]; then
    exec >>"${BACKUP_LOG}" 2>&1
  else
    exec > >(tee -a "${BACKUP_LOG}") 2>&1
  fi
  BACKUP_ACTIVE_RUN="$(backup_active)"
  if [ -z "${BACKUP_STOP_FORCED:-}" ] && [ -n "${BACKUP_ACTIVE_RUN}" ] && [ "${BACKUP_ACTIVE_RUN}" != "${BACKUP_RUN_ID}" ]; then
    backup_stopping "refusing to stop, run [${BACKUP_ACTIVE_RUN}] is the active one"
  else
    if [ "${BACKUP_STAGE}" = "tertiary" ]; then
      read -r BACKUP_FLUSH_PENDING BACKUP_FLUSH_SECONDS < <(backup_flushing)
      backup_stopping "stopping run [${BACKUP_RUN_ID}], flushing [$(backup_sized "${BACKUP_FLUSH_PENDING}")] MB, estimated to stop in [${BACKUP_FLUSH_SECONDS}] s"
    else
      backup_stopping "stopping run [${BACKUP_RUN_ID}]"
    fi
    : >"${BACKUP_STAGE_DIR}/.stopped"
    pkill -CONT -f "backup\.sh start ${BACKUP_RUN_ID} --stage ${BACKUP_STAGE}" 2>/dev/null
    pkill -TERM -f "backup\.sh start ${BACKUP_RUN_ID} --stage ${BACKUP_STAGE}" 2>/dev/null &&
      backup_stopping "signalled the runner to clean up and exit"
    stage_stop || true
    backup_stopping "stopped run [${BACKUP_RUN_ID}]"
  fi
  if [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && [ "${BACKUP_STOP_SECONDS}" -gt 0 ]; then
    backup_await "${BACKUP_RUN_PATH}" "${BACKUP_STOP_SECONDS}" ||
      backup_log WARN "run [${BACKUP_RUN_ID}] is still running after [${BACKUP_STOP_SECONDS}] s"
    backup_status "${BACKUP_RUN_PATH}" "${BACKUP_STAGE}" >&3 || true
  fi
  exit 0
fi

if [ -z "${BACKUP_DETACHED:-}" ] && [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && { [ -t 1 ] || [ "${BACKUP_TIMEOUT_HOURS}" = "0" ]; }; then
  export BACKUP_DETACHED=1
  set -m
  nohup "$0" start "${BACKUP_RUN_ID}" --stage "${BACKUP_STAGE}" >>"${BACKUP_LOG}" 2>&1 &
  BACKUP_CHILD=$!
  set +m
  disown
  backup_announce "${BACKUP_STAGE}"
  while kill -0 "${BACKUP_CHILD}" 2>/dev/null && [ ! -f "${BACKUP_STAGE_DIR}/status.json" ]; do sleep 1; done
  if [ ! -f "${BACKUP_STAGE_DIR}/status.json" ]; then
    backup_log ERROR "run [${BACKUP_RUN_ID}] exited before recording [${BACKUP_STAGE}], see [${BACKUP_LOG}]"
    exit 1
  fi
  backup_tail "${BACKUP_RUN_ID}" "" "${BACKUP_STAGE}"
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
    backup_log ERROR "another backup run holds [${BACKUP_LOCK}], refusing to start"
    exit 3
  fi
fi

BACKUP_MAIN_PID=$$
BACKUP_STARTED="$(date +%s)"
trap 'backup_interrupted' TERM INT
[ -n "${BACKUP_RUN_GIVEN}" ] || [ -n "${BACKUP_RUN_ID_PASSED:-}" ] ||
  backup_log WARN "started as its own run [${BACKUP_RUN_ID}], pass a run id to join the stages of one run"
backup_started "${BACKUP_STAGE}"
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
backup_document "${BACKUP_STATE_RUNNING}" false "${BACKUP_STARTED}" "$(( BACKUP_STARTED + BACKUP_HEARTBEAT_GRACE ))"
backup_progress "${BACKUP_RUN_PATH}" "${BACKUP_STAGE}"
backup_heartbeat 9>&- &
BACKUP_HEARTBEAT_PID=$!

BACKUP_RESULT=0
stage_start || BACKUP_RESULT=$?
backup_settle
BACKUP_REACHED="${BACKUP_STATE_COMPLETE}"
[ "${BACKUP_RESULT}" -eq 0 ] || BACKUP_REACHED="${BACKUP_STATE_FAILED}"
backup_document "${BACKUP_REACHED}" "$([ "${BACKUP_RESULT}" -eq 0 ] && echo true || echo false)" "${BACKUP_STARTED}"
BACKUP_DURATION="$(backup_tail_field "${BACKUP_STAGE_DIR}/status.json" duration_s)"
BACKUP_MOVED="$(backup_tail_field "${BACKUP_STAGE_DIR}/status.json" size_mb)"
backup_banner "finished [${BACKUP_STAGE}] of run [${BACKUP_RUN_ID}] as [${BACKUP_REACHED}]" \
  "elapsed   [$(backup_elapsed "${BACKUP_DURATION:-0}")]" \
  "files     [${BACKUP_FILES}] transferred, [${BACKUP_FILES_CREATED}] created, [${BACKUP_FILES_DELETED}] deleted, [${BACKUP_FILES_HELD}] held" \
  "size      [$(backup_sized "${BACKUP_SIZE}")] MB transferred, [$(backup_sized "${BACKUP_SENT}")] MB sent, [$(backup_sized "${BACKUP_SIZE_HELD}")] MB held" \
  "rate      [$(backup_rated "${BACKUP_MOVED:-0}" "${BACKUP_DURATION:-0}")] MB/s transferred" \
  "disk      [$(backup_percent "${BACKUP_USAGE}")] percent used" \
  "status    [${BACKUP_STAGE_DIR}/status.json]"
[ "${BACKUP_STAGE}" = "tertiary" ] || backup_progress "${BACKUP_RUN_PATH}" "${BACKUP_STAGE}"
backup_finished "${BACKUP_STAGE}" "${BACKUP_STAGE_DIR}/status.json"
exit "${BACKUP_RESULT}"
