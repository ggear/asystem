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
BACKUPS_SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10)
BACKUPS_REMOTE="${BACKUPS_REMOTE:-/usr/local/bin/abackup}"
BACKUPS_TIMEOUT_DEFAULT="${BACKUPS_TIMEOUT_DEFAULT:-6}"
BACKUPS_TIMEOUT_HOURS="${BACKUPS_TIMEOUT_HOURS:-}"

backups_log() {
  local level="$1"; shift
  case "${level}" in
  WARN | ERRS) printf '[%-4s %8s] %s\n' "${level}" "$(date '+%H:%M:%S')" "$*" >&2 ;;
  *) printf '[%-4s %8s] %s\n' "${level}" "$(date '+%H:%M:%S')" "$*" ;;
  esac
}

backups_help() {
  local out=2
  [ "${1:-}" = "help" ] && out=1
  {
    echo "Usage: ${0##*/} [command]"
    echo
    echo "  start  dispatch every enrolled host's backup, serially, detached"
    echo "  stop   stop every active run on every enrolled host"
    echo "  list   list every enrolled host's run history"
    echo "  help   this text, default command when given none"
  } >&"${out}"
}

backups_hosts() {
  [ -f "${BACKUPS_CONFIG}" ] || { backups_log ERRS "could not find [${BACKUPS_CONFIG}] to read the enrolled hosts from"; return 1; }
  jq -r '.asystem.schema[]?.host // empty' "${BACKUPS_CONFIG}" 2>/dev/null
}

backups_midnight() {
  local midnight
  midnight="$(date -d "00:00:00" +%s 2>/dev/null)"
  [ -n "${midnight}" ] || midnight="$(date -v0H -v0M -v0S +%s 2>/dev/null)"
  [ -n "${midnight}" ] && printf '%s' "$(( midnight + 86400 ))"
}

backups_timeout_hours() {
  local now midnight seconds hours
  [ -n "${BACKUPS_TIMEOUT_HOURS}" ] && { printf '%s' "${BACKUPS_TIMEOUT_HOURS}"; return 0; }
  now="$(date +%s)"
  midnight="$(backups_midnight)"
  if [ -z "${midnight}" ]; then
    backups_log WARN "could not resolve local midnight to bound the run timeout, using [${BACKUPS_TIMEOUT_DEFAULT}] hours"
    printf '%s' "${BACKUPS_TIMEOUT_DEFAULT}"
    return 0
  fi
  seconds=$(( midnight - now ))
  hours=$(( (seconds + 3599) / 3600 ))
  [ "${hours}" -ge 1 ] || hours=1
  printf '%s' "${hours}"
}

backups_header() {
  printf '\n== %s ==\n\n' "$1"
}

# shellcheck disable=SC2029
backups_dispatch() {
  local host="$1" remote="$2"
  backups_header "${host}"
  ssh "${BACKUPS_SSH_OPTS[@]}" "${BACKUPS_SSH_USER}@${host}" "${remote}" ||
    backups_log ERRS "could not reach [${host}], see above"
}

backups_start_one() {
  backups_dispatch "$1" \
    "set -m; nohup env BACKUP_TIMEOUT_HOURS=${BACKUPS_RUN_HOURS} ${BACKUPS_REMOTE} start ${BACKUPS_RUN_ID} --scrub </dev/null >/dev/null 2>&1 & disown; echo dispatched run [${BACKUPS_RUN_ID}] with timeout [${BACKUPS_RUN_HOURS}] hours"
}

backups_stop_one() {
  backups_dispatch "$1" "${BACKUPS_REMOTE} stop"
}

backups_list_one() {
  backups_dispatch "$1" "${BACKUPS_REMOTE} list"
}

backups_each() {
  local action="$1" host found=0
  while IFS= read -r host; do
    [ -n "${host}" ] || continue
    found=1
    "${action}" "${host}"
  done < <(backups_hosts)
  if [ "${found}" -eq 0 ]; then
    backups_log ERRS "no enrolled hosts found in [${BACKUPS_CONFIG}]"
    return 1
  fi
  return 0
}

backups_start() {
  BACKUPS_RUN_ID="$(date +%Y-%m-%d_%H-%M-%S)"
  BACKUPS_RUN_HOURS="$(backups_timeout_hours)"
  backups_log INFO "starting suite run [${BACKUPS_RUN_ID}] with timeout [${BACKUPS_RUN_HOURS}] hours, expiring before the 01:00 scheduled run"
  backups_each backups_start_one
}

backups_stop() {
  backups_each backups_stop_one
}

backups_list() {
  backups_each backups_list_one
}

# shellcheck disable=SC2317
if [ -n "${BACKUPS_SOURCE_ONLY:-}" ]; then return 0 2>/dev/null || exit 0; fi

BACKUPS_COMMAND="${1:-help}"
case "${BACKUPS_COMMAND}" in
help)
  backups_help help
  exit 0
  ;;
start | stop | list)
  command -v ssh >/dev/null 2>&1 || { backups_log ERRS "ssh is required and was not found"; exit 1; }
  command -v jq >/dev/null 2>&1 || { backups_log ERRS "jq is required and was not found"; exit 1; }
  "backups_${BACKUPS_COMMAND}"
  ;;
*)
  backups_log ERRS "unknown command [${BACKUPS_COMMAND}]"
  backups_help
  exit 2
  ;;
esac
