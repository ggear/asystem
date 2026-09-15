#!/usr/bin/env bash

# An estate-wide dispatcher over ssh, deliberately outside backup.sh, which does not change for this.
#
# The per-run timeout is computed here, not read from backup.sh's default: hours from now until local
# midnight, so a suite-wide run is guaranteed to stop itself before the 01:00 scheduled run reaches
# backup_active's already-running check. The reaper is untouched on purpose - backup.sh's own heartbeat
# already keeps the retained tertiary status fresh, which is what the reaper watches to defer reaping,
# whoever triggered the run.
#
# Set BACKUPS_SOURCE_ONLY=1 to source this file for its functions alone, which is how the unit tests
# reach them.

set -uo pipefail

BACKUPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUPS_CONFIG="${BACKUPS_CONFIG:-${BACKUPS_ROOT}/config.json}"
BACKUPS_SSH_USER="${BACKUPS_SSH_USER:-root}"
BACKUPS_SSH_OPTS=(-n -o BatchMode=yes -o ConnectTimeout=10)
BACKUPS_REMOTE="${BACKUPS_REMOTE:-/usr/local/bin/abackup}"
BACKUPS_TIMEOUT_DEFAULT="${BACKUPS_TIMEOUT_DEFAULT:-6}"
BACKUPS_TIMEOUT_HOURS="${BACKUPS_TIMEOUT_HOURS:-}"
BACKUPS_SCHEDULED_HOUR=1
BACKUPS_HOSTS_LABEL="*******-***"
BACKUPS_EXIT_PARTIAL=3
BACKUPS_RUN_HOURS=""
BACKUPS_SETTLE_SECONDS="${BACKUPS_SETTLE_SECONDS:-5}"
BACKUPS_RUN_ID="${BACKUPS_RUN_ID:-}"
BACKUPS_INTERRUPTED=0
BACKUPS_SCRUB="${BACKUPS_SCRUB:-0}"
BACKUPS_GIVEN=()
BACKUPS_REJECT=""

backups_log() {
  local level="$1"
  shift
  case "${level}" in
  WARN | ERRS) printf '[%-4s %-9s %8s] %s\n' "${level}" "" "$(date '+%H:%M:%S')" "$*" >&2 ;;
  *) printf '[%-4s %-9s %8s] %s\n' "${level}" "" "$(date '+%H:%M:%S')" "$*" ;;
  esac
}

backups_help() {
  local out=2
  [ "${1:-}" = "help" ] && out=1
  {
    echo "Usage: ${0##*/} [command] [options]"
    echo
    echo "  start    start runs on all hosts, then follow them until interrupted"
    echo "  stop     stop every active run on every host"
    echo "  tail     follow every host's newest run until interrupted"
    echo "  list     list every host's run history"
    echo "  help     this text, default command when given none"
    echo
    echo "  --scrub  scrub each host's backup disk"
  } >&"${out}"
}

backups_hosts() {
  [ -f "${BACKUPS_CONFIG}" ] || {
    backups_log ERRS "could not find [${BACKUPS_CONFIG}] to read the enrolled hosts from"
    return 1
  }
  jq -r '.asystem.schema[]?.host // empty' "${BACKUPS_CONFIG}" 2>/dev/null
}

backups_scheduled() {
  local now scheduled
  now="$(date +%s)"
  scheduled="$(date -d "today ${BACKUPS_SCHEDULED_HOUR}:00:00" +%s 2>/dev/null)"
  [ -n "${scheduled}" ] || scheduled="$(date -v"${BACKUPS_SCHEDULED_HOUR}"H -v0M -v0S +%s 2>/dev/null)"
  [ -n "${scheduled}" ] || return 0
  [ "${scheduled}" -gt "${now}" ] || scheduled=$((scheduled + 86400))
  printf '%s' "${scheduled}"
}

backups_timeout_hours() {
  local now scheduled seconds hours
  [ -n "${BACKUPS_TIMEOUT_HOURS}" ] && {
    printf '%s' "${BACKUPS_TIMEOUT_HOURS}"
    return 0
  }
  now="$(date +%s)"
  scheduled="$(backups_scheduled)"
  if [ -z "${scheduled}" ]; then
    backups_log WARN "could not resolve the next [$(printf '%02d' "${BACKUPS_SCHEDULED_HOUR}"):00] run to bound the run timeout, using [${BACKUPS_TIMEOUT_DEFAULT}] hours"
    printf '%s' "${BACKUPS_TIMEOUT_DEFAULT}"
    return 0
  fi
  seconds=$((scheduled - now))
  hours=$(((seconds - 1) / 3600))
  if [ "${hours}" -lt 1 ]; then
    hours=1
    backups_log WARN "less than an hour until the [$(printf '%02d' "${BACKUPS_SCHEDULED_HOUR}"):00] run, so this one cannot expire before it"
  fi
  printf '%s' "${hours}"
}

# shellcheck disable=SC2029
backups_dispatch() {
  local host="$1" remote="$2" status=0
  ssh "${BACKUPS_SSH_OPTS[@]}" "${BACKUPS_SSH_USER}@${host}" "${remote}" 2>/dev/null |
    awk -v host="${host}" '
      /^[[:space:]]*$/ { if (shown) pending = 1; next }
      { if (!shown) { printf "\n== %s ==\n\n", host; shown = 1 }
        else if (pending) { print "" }
        pending = 0
        print }'
  status=$?
  return "${status}"
}

# shellcheck disable=SC2029
backups_start_one() {
  local host="$1" scrub="" status=0
  [ "${BACKUPS_SCRUB}" = "1" ] && scrub=" --scrub"
  ssh "${BACKUPS_SSH_OPTS[@]}" "${BACKUPS_SSH_USER}@${host}" \
    "set -m; nohup env BACKUP_TIMEOUT_HOURS=${BACKUPS_RUN_HOURS} ${BACKUPS_REMOTE} start ${BACKUPS_RUN_ID}${scrub} </dev/null >/dev/null 2>&1 & disown" \
    >/dev/null 2>&1 || status=$?
  [ "${status}" -eq 0 ] || return "${status}"
  backups_log INFO "dispatched run [${BACKUPS_RUN_ID}] to [${host}] with timeout [${BACKUPS_RUN_HOURS}] hours and scrub [$([ "${BACKUPS_SCRUB}" = "1" ] && echo on || echo off)]"
}

backups_tail_one() {
  backups_dispatch "$1" "${BACKUPS_REMOTE} tail"
}

backups_stop_one() {
  backups_dispatch "$1" "${BACKUPS_REMOTE} stop"
}

backups_list_one() {
  backups_dispatch "$1" "${BACKUPS_REMOTE} list"
}

# shellcheck disable=SC2329
backups_interrupt() {
  BACKUPS_INTERRUPTED=1
  echo >&2
  backups_log WARN "tailing stopped, every dispatched run continues on its own host"
  backups_log WARN "follow them again with [${0##*/} tail] or end them with [${0##*/} stop]"
}

backups_each() {
  local action="$1" host found=0 failed=0 hosts=() enrolled
  enrolled="$(backups_hosts)" || return 1
  mapfile -t hosts <<<"${enrolled}"
  for host in ${hosts[@]+"${hosts[@]}"}; do
    [ -n "${host}" ] || continue
    [ "${BACKUPS_INTERRUPTED}" -eq 0 ] || return 130
    found=$((found + 1))
    "${action}" "${host}" || failed=$((failed + 1))
  done
  if [ "${found}" -eq 0 ]; then
    backups_log ERRS "no enrolled hosts found in [${BACKUPS_CONFIG}]"
    return 1
  fi
  [ "${failed}" -eq 0 ] || return "${BACKUPS_EXIT_PARTIAL}"
  return 0
}

backups_start() {
  local status=0
  printf '\n== %s ==\n\n' "${BACKUPS_HOSTS_LABEL}"
  BACKUPS_RUN_ID="$(date +%Y-%m-%d_%H-%M-%S)"
  BACKUPS_RUN_HOURS="$(backups_timeout_hours)"
  backups_each backups_start_one || status=$?
  [ "${status}" -eq 1 ] && return 1
  sleep "${BACKUPS_SETTLE_SECONDS}"
  backups_tail || status="$?"
  printf '\n'
  return "${status}"
}

backups_tail() {
  local status=0
  trap 'backups_interrupt' INT
  backups_each backups_tail_one || status=$?
  trap - INT
  [ "${status}" -eq 130 ] && status=0
  printf '\n'
  return "${status}"
}

backups_stop() {
  backups_each backups_stop_one
  printf '\n'
}

backups_list() {
  backups_each backups_list_one
  printf '\n'
}

# shellcheck disable=SC2317
if [ -n "${BACKUPS_SOURCE_ONLY:-}" ]; then return 0 2>/dev/null || exit 0; fi

while [ "$#" -gt 0 ]; do
  case "$1" in
  --scrub) BACKUPS_SCRUB=1 ;;
  -*) BACKUPS_REJECT="$1" ;;
  *) BACKUPS_GIVEN+=("$1") ;;
  esac
  shift
done
set -- ${BACKUPS_GIVEN[@]+"${BACKUPS_GIVEN[@]}"}
if [ -n "${BACKUPS_REJECT}" ]; then
  backups_log ERRS "unknown option [${BACKUPS_REJECT}]"
  backups_help
  exit 2
fi

BACKUPS_COMMAND="${1:-help}"
if [ "${BACKUPS_SCRUB}" = "1" ] && [ "${BACKUPS_COMMAND}" != "start" ]; then
  backups_log ERRS "only start scrubs, not command [${BACKUPS_COMMAND}]"
  backups_help
  exit 2
fi
case "${BACKUPS_COMMAND}" in
help)
  backups_help help
  exit 0
  ;;
start | stop | tail | list)
  command -v ssh >/dev/null 2>&1 || {
    backups_log ERRS "ssh is required and was not found"
    exit 1
  }
  command -v jq >/dev/null 2>&1 || {
    backups_log ERRS "jq is required and was not found"
    exit 1
  }
  "backups_${BACKUPS_COMMAND}"
  ;;
*)
  backups_log ERRS "unknown command [${BACKUPS_COMMAND}]"
  backups_help
  exit 2
  ;;
esac
