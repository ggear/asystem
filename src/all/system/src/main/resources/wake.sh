#!/bin/bash

################################################################################
# awake, undo asleep when power returns before the UPS runs out
#
# Usage
#   awake [--health-timeout SECONDS] [--share-timeout SECONDS] [--quiet] [--dry-run]
#
# Options
#   --health-timeout  seconds to wait for starting or unhealthy containers to turn healthy,
#                     default 60, 0 to report without waiting
#   --share-timeout   seconds to wait for each samba share to answer before docker starts,
#                     default 10, the shares are probed together, 0 to skip, a share that is
#                     not up is a warning and stays on its automount
#   --quiet           drop DEBUG lines
#   --dry-run         print the steps, change nothing
#
# Exit codes
#   0  ok           every post-condition verified
#   1  error        a post-condition failed, a unit not active or a mount missing
#   2  usage        bad arguments
#   3  precondition not root
#   4  timeout      a step hit its limit
#   6  unhealthy    a recorded container is not running or is unhealthy
#
# Run as root on the host, it restores from /run/asleep.state.
# The last line is RESULT awake status=<code> reason=<ok|error|timeout|unhealthy>
################################################################################

set -uo pipefail

################################################################################
# Logging
################################################################################
DRY_RUN=false
QUIET=false
HEALTH_TIMEOUT=60
SHARE_TIMEOUT=10
RUN_ID="$(date +%s)-$$"
LOG_FILE="${AWAKE_LOG:-/run/awake.log}"
STATE="${ASLEEP_STATE:-/run/asleep.state}"
STARTED="${EPOCHREALTIME/./}"
SECTION=""
SECTION_STARTED=0

log_line() {
  local line
  printf -v line '%(%FT%T%z)T %-5s %s' -1 "$1" "$2"
  printf '%s\n' "${line}"
  [[ "${DRY_RUN}" == "true" ]] || { printf '%s\n' "${line}" >>"${LOG_FILE}"; } 2>/dev/null
  return 0
}
log_info() { log_line INFO "$*"; }
log_warn() { log_line WARN "$*"; }
log_error() { log_line ERROR "$*"; }
log_debug() { [[ "${QUIET}" == "true" ]] || log_line DEBUG "$*"; }
log_out() {
  local line
  while IFS= read -r line; do log_line OUT "${line}"; done
}
elapsed() { echo $(((${EPOCHREALTIME/./} - $1) / 1000)); }
short() { [[ ${#1} -le 100 ]] && echo "$1" || echo "${1:0:100}..."; }

section() {
  [[ -z "${SECTION}" ]] || log_debug "Section [${SECTION}] done, took [$(elapsed "${SECTION_STARTED}")] ms"
  SECTION="$1"
  SECTION_STARTED="${EPOCHREALTIME/./}"
  log_info "Section [$1]"
}

FAILED=()
WARNED=()
fail() {
  log_error "Failed, $*"
  FAILED+=("$*")
}

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ $*"
    return 0
  fi
  local started="${EPOCHREALTIME/./}" rc
  log_debug "Run [$(short "$*")]"
  "$@" 2>&1 | log_out
  rc="${PIPESTATUS[0]}"
  log_debug "Ran [$(short "$*")], exit code [${rc}], took [$(elapsed "${started}")] ms"
  return "${rc}"
}

TIMEOUTS=0
attempt() {
  local seconds="$1" rc
  shift
  run timeout "${seconds}" "$@"
  rc=$?
  if ((rc == 124)); then
    TIMEOUTS=$((TIMEOUTS + 1))
    log_warn "Timed out after [${seconds}] seconds, command [$(short "$*")]"
  fi
  return "${rc}"
}

try() {
  local seconds="$1"
  shift
  attempt "${seconds}" "$@" || {
    log_warn "Step failed, command [$(short "$*")]"
    WARNED+=("$*")
  }
}

has() { command -v "$1" >/dev/null 2>&1; }

startable() {
  local unit dependency
  while read -r unit; do
    [[ -n "${unit}" ]] || continue
    [[ "$(systemctl show --property=LoadState --value "${unit}" 2>/dev/null)" == "masked" ]] && continue
    for dependency in $(systemctl show --property=Requires,BindsTo,Requisite --value "${unit}" 2>/dev/null); do
      if [[ "$(systemctl show --property=LoadState --value "${dependency}" 2>/dev/null)" == "masked" ]]; then
        log_debug "Unit [${unit}] left stopped, requires masked [${dependency}]" >&2
        continue 2
      fi
    done
    printf '%s\n' "${unit}"
  done
}

units() {
  if [[ "$1" == "any" ]]; then
    systemctl list-units --state="$2" --plain --no-legend --no-pager | awk '{print $1}'
  else
    systemctl list-units --type="$1" --state="$2" --plain --no-legend --no-pager | awk '{print $1}'
  fi
}

snapshot() {
  local label="$1" line
  log_debug "Snapshot [${label}], kernel [$(uname -r)], uptime [$(cut -d' ' -f1 /proc/uptime)] s"
  log_debug "Snapshot [${label}], load [$(cut -d' ' -f1-3 /proc/loadavg)]"
  log_debug "Snapshot [${label}], swap [$(swapon --noheadings --show=NAME 2>/dev/null | xargs)]"
  while IFS= read -r line; do log_debug "Snapshot [${label}], ${line}"; done < <(
    awk '/^(MemAvailable|Dirty|Writeback|SwapFree):/ {
      printf "%s [%s] kB\n", substr($1, 1, length($1) - 1), $2
    }' /proc/meminfo
  )
  while IFS= read -r line; do log_debug "Snapshot [${label}], ${line}"; done < <(
    findmnt --raw --noheadings --output TARGET,SOURCE,FSTYPE,OPTIONS |
      awk '$2 ~ /^\/dev\// || $3 ~ /^(cifs|nfs|nfs4|autofs)$/ {
        printf "mount [%s], type [%s], options [%s]\n", $1, $3, substr($4, 1, 40)
      }'
  )
  if has docker && systemctl is-active --quiet docker.service; then
    while IFS= read -r line; do
      log_debug "Snapshot [${label}], ${line}"
    done < <(docker ps --format 'container [{{.Names}}], status [{{.Status}}]')
  fi
  log_debug "Snapshot [${label}], services [$(units service running | wc -l)], timers [$(units timer active | wc -l)]"
  log_debug "Snapshot [${label}], automounts [$(units automount active | wc -l)], failed [$(units any failed | wc -l)]"
}

explain() {
  local name="$1" line started
  local checks='{{range .State.Health.Log}}{{.Start.Unix}} {{.End.Format "15:04:05"}} exit [{{.ExitCode}}] '
  checks+='{{printf "%.100q" .Output}}{{"\n"}}{{end}}'
  log_warn "Container [${name}] health [$(docker inspect --format '{{.State.Health.Status}}' "${name}")]"
  log_warn "Container [${name}] failing streak [$(docker inspect --format '{{.State.Health.FailingStreak}}' "${name}")]"
  started="$(date -d "$(docker inspect --format '{{.State.StartedAt}}' "${name}")" +%s 2>/dev/null || echo 0)"
  while IFS= read -r line; do
    log_warn "Container [${name}] check ${line}"
  done < <(docker inspect --format "${checks}" "${name}" | awk -v started="${started}" 'NF && $1 >= started {sub(/^[^ ]+ /, ""); print}' | tail -n 2)
  docker logs --tail 5 "${name}" 2>&1 | log_out
}

recorded() { awk -v kind="$1" '$1 == kind {print $2}' "${STATE}" 2>/dev/null; }
was() { grep -qxF "$1" "${STATE}" 2>/dev/null; }

################################################################################
# Arguments
################################################################################
usage() {
  log_error "Usage, awake [--health-timeout SECONDS] [--share-timeout SECONDS] [--quiet] [--dry-run]"
  exit 2
}
while [[ $# -gt 0 ]]; do
  case "$1" in
  -n | --dry-run) DRY_RUN=true ;;
  -q | --quiet) QUIET=true ;;
  --health-timeout)
    [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || usage
    HEALTH_TIMEOUT="$2"
    shift
    ;;
  --share-timeout)
    [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || usage
    SHARE_TIMEOUT="$2"
    shift
    ;;
  *) usage ;;
  esac
  shift
done
[[ ${EUID} -eq 0 ]] || {
  log_error "Must run as root"
  exit 3
}
trap 'log_debug "Exiting, exit code [$?]"' EXIT
[[ "${DRY_RUN}" == "true" ]] || : >"${LOG_FILE}"

MODE="$(recorded mode)"
log_info "Starting, host [$(hostname)], dry run [${DRY_RUN}], run [${RUN_ID}]"
log_debug "User [$(id -un)], pid [$$], log [${LOG_FILE}], state [${STATE}], health timeout [${HEALTH_TIMEOUT}] seconds"
if [[ -s "${STATE}" ]]; then
  log_info "Restoring from [${STATE}], mode [${MODE:-unknown}]"
else
  log_warn "No record at [${STATE}], restoring from fstab only"
fi
snapshot before

################################################################################
# Root filesystem
################################################################################
section "Root filesystem"
if findmnt --noheadings --output OPTIONS --target / | grep -Eq '(^|,)ro(,|$)'; then
  log_info "Root is read only, remounting writable"
  try 30 mount -o remount,rw /
else
  log_debug "Root already writable"
fi

################################################################################
# Devices
################################################################################
section "Devices"
for SCAN in /sys/class/scsi_host/host*/scan; do
  [[ -e "${SCAN}" ]] || continue
  if [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ rescan [${SCAN}]"
  elif echo "- - -" >"${SCAN}"; then
    log_debug "Rescanned [${SCAN}]"
  else
    log_warn "Rescan failed, host [${SCAN}]"
  fi
done
try 60 udevadm settle

################################################################################
# Mount
################################################################################
section "Mount"
if [[ -s "${STATE}" ]]; then
  mapfile -t REMOUNTS < <(awk '$1 == "remount" {print $2}' "${STATE}" | tac)
  mapfile -t MOUNTS < <(awk '$1 == "mount" {print $2}' "${STATE}" | tac)
else
  REMOUNTS=()
  mapfile -t MOUNTS < <(
    findmnt --fstab --noheadings --raw --output TARGET,FSTYPE,OPTIONS |
      awk '$1 ~ /^\// && $1 != "/" && $2 != "swap" && $3 !~ /(^|,)noauto(,|$)/ {print length($1), $1}' |
      sort -n | cut -d' ' -f2-
  )
fi
log_debug "Remount order [${REMOUNTS[*]:-}], mount order [${MOUNTS[*]:-}]"
for TARGET in "${REMOUNTS[@]}"; do
  [[ "${TARGET}" == "/" ]] && continue
  log_info "Mount [${TARGET}] to remount writable"
  try 30 mount -o remount,rw "${TARGET}"
done
for TARGET in "${MOUNTS[@]}"; do
  if mountpoint -q "${TARGET}"; then
    log_debug "Mount [${TARGET}] skipped, already mounted"
    continue
  fi
  if was "automount $(systemd-escape --path --suffix=automount "${TARGET}")"; then
    log_debug "Mount [${TARGET}] skipped, its automount will mount it"
    continue
  fi
  for ATTEMPT in 1 2 3 4 5; do
    if [[ "${DRY_RUN}" == "true" ]]; then
      log_info "+ mount [${TARGET}]"
      break
    fi
    log_debug "Mount [${TARGET}], attempt [${ATTEMPT}]"
    timeout 30 mount "${TARGET}" 2>&1 | log_out
    RC="${PIPESTATUS[0]}"
    if ((RC == 0)); then
      log_info "Mount [${TARGET}] mounted"
      break
    fi
    ((RC != 124)) || TIMEOUTS=$((TIMEOUTS + 1))
    ((ATTEMPT < 5)) || log_warn "Mount [${TARGET}] failed after [${ATTEMPT}] attempts, exit code [${RC}]"
    udevadm settle --timeout=3 >/dev/null 2>&1
    sleep 2
  done
done

################################################################################
# Swap and journal
################################################################################
section "Swap and journal"
if was swap || [[ ! -s "${STATE}" ]]; then
  try 60 swapon -a
fi
if [[ "${MODE}" != "shallow" ]]; then
  run timeout 30 systemctl restart systemd-journal-flush.service || try 30 journalctl --flush
else
  log_debug "Journal untouched, mode [shallow]"
fi

################################################################################
# Mount readiness
################################################################################
section "Mount readiness"
for TARGET in "${MOUNTS[@]}"; do
  if [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ ls [${TARGET}]"
    continue
  fi
  DEADLINE=$((SECONDS + 5))
  until timeout 5 ls -A "${TARGET}" >/dev/null 2>&1; do
    if ((SECONDS >= DEADLINE)); then
      log_warn "Mount [${TARGET}] not listable after [5] seconds, docker may start without it"
      WARNED+=("not listable ${TARGET}")
      continue 2
    fi
    sleep 1
  done
  log_debug "Mount [${TARGET}] ready"
done

################################################################################
# Shares
################################################################################
section "Shares"
mapfile -t AUTOMOUNTS < <(recorded automount | startable)
[[ ${#AUTOMOUNTS[@]} -eq 0 ]] || try 60 systemctl start "${AUTOMOUNTS[@]}"
mapfile -t SHARES < <(findmnt --fstab --noheadings --raw --output TARGET,FSTYPE | awk '$2 == "cifs" {print $1}')
SHARE_PIDS=()
for TARGET in "${SHARES[@]}"; do
  if [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ probe [${TARGET}]"
  elif ((SHARE_TIMEOUT == 0)); then
    log_debug "Share [${TARGET}] not probed, share timeout [0]"
  else
    timeout "${SHARE_TIMEOUT}" ls -A "${TARGET}" >/dev/null 2>&1 &
    SHARE_PIDS+=("$!")
  fi
done
for INDEX in "${!SHARE_PIDS[@]}"; do
  RC=0
  wait "${SHARE_PIDS[INDEX]}" || RC=$?
  if ((RC == 0)); then
    log_debug "Share [${SHARES[INDEX]}] ready"
  elif ((RC == 124)); then
    log_warn "Share [${SHARES[INDEX]}] not available within [${SHARE_TIMEOUT}] seconds, docker starts without it"
    WARNED+=("share not available ${SHARES[INDEX]}")
  else
    log_warn "Share [${SHARES[INDEX]}] refused, exit code [${RC}], its server may still be asleep, docker starts without it"
    WARNED+=("share not available ${SHARES[INDEX]}")
  fi
done

################################################################################
# Network leases
################################################################################
section "Network leases"
while read -r COMMAND; do
  [[ -n "${COMMAND}" ]] || continue
  read -ra ARGV <<<"${COMMAND}"
  PIDFILE=""
  for INDEX in "${!ARGV[@]}"; do
    [[ "${ARGV[INDEX]}" == "-pf" ]] && PIDFILE="${ARGV[INDEX + 1]:-}"
  done
  if [[ -n "${PIDFILE}" && -s "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
    log_debug "Lease client already running, command [${COMMAND}]"
  elif [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ start [${COMMAND}]"
  else
    log_info "Lease client to start, command [${COMMAND}]"
    try 30 "${ARGV[@]}"
  fi
done < <(awk '$1 == "dhclient" {$1 = ""; print substr($0, 2)}' "${STATE}" 2>/dev/null)

################################################################################
# Docker
################################################################################
section "Docker"
if was docker; then
  try 120 systemctl start containerd.service docker.socket docker.service
else
  log_debug "Docker was not stopped"
fi

################################################################################
# Units
################################################################################
section "Units"
mapfile -t SOCKETS < <(recorded socket | startable)
mapfile -t SERVICES < <(recorded service | startable)
mapfile -t TIMERS < <(recorded timer | startable)
log_debug "Sockets [${#SOCKETS[@]}], services [${#SERVICES[@]}], timers [${#TIMERS[@]}]"
[[ ${#SOCKETS[@]} -eq 0 ]] || try 60 systemctl start "${SOCKETS[@]}"
[[ ${#SERVICES[@]} -eq 0 ]] || try 300 systemctl start "${SERVICES[@]}"
if was auditd && has service; then
  try 30 service auditd start
fi
[[ ${#TIMERS[@]} -eq 0 ]] || try 60 systemctl start "${TIMERS[@]}"

################################################################################
# Containers
################################################################################
section "Containers"
mapfile -t CONTAINERS < <(recorded container)
for ID in "${CONTAINERS[@]}"; do log_info "Container [${ID}] to start"; done
[[ ${#CONTAINERS[@]} -eq 0 ]] || try 300 docker start "${CONTAINERS[@]}"
try 300 systemctl start default.target

################################################################################
# Health
################################################################################
section "Health"
WAITED=0
if [[ "${DRY_RUN}" != "true" ]] && has docker; then
  PENDING=(--filter health=starting --filter health=unhealthy)
  while [[ -n "$(docker ps --quiet "${PENDING[@]}")" ]] && ((WAITED < HEALTH_TIMEOUT)); do
    if ((WAITED % 15 == 0)); then
      NAMES="$(docker ps --format '{{.Names}}' "${PENDING[@]}" | xargs)"
      log_debug "Waiting for health, waited [${WAITED}] seconds, pending [${NAMES}]"
    fi
    sleep 3
    WAITED=$((WAITED + 3))
  done
fi
UNHEALTHY=()
STARTING=()
if has docker; then
  mapfile -t UNHEALTHY < <(docker ps --format '{{.Names}}' --filter health=unhealthy)
  mapfile -t STARTING < <(docker ps --format '{{.Names}}' --filter health=starting)
fi
log_debug "Waited [${WAITED}] seconds, unhealthy [${UNHEALTHY[*]:-}], still starting [${STARTING[*]:-}]"
for NAME in "${UNHEALTHY[@]}" "${STARTING[@]}"; do explain "${NAME}"; done

################################################################################
# Verdict
################################################################################
section "Verdict"
MISSING=()
while read -r TARGET OPTIONS; do
  [[ "${OPTIONS}" =~ (^|,)(noauto|x-systemd.automount)(,|$) ]] && continue
  mountpoint -q "${TARGET}" && continue
  if [[ "${OPTIONS}" =~ (^|,)nofail(,|$) ]] && ! was "mount ${TARGET}" && ! was "remount ${TARGET}"; then
    log_info "Mount [${TARGET}] not mounted, nofail and not recorded so left alone"
    continue
  fi
  MISSING+=("${TARGET}")
done < <(findmnt --fstab --noheadings --raw --output TARGET,OPTIONS | awk '$1 ~ /^\// && $1 != "/"')
WRITABLE_ROOT=true
findmnt --noheadings --output OPTIONS --target / | grep -Eq '(^|,)ro(,|$)' && WRITABLE_ROOT=false
snapshot after
if [[ "${DRY_RUN}" == "true" ]]; then
  log_info "Dry run complete, nothing changed"
  exit 0
fi
for KIND in automount socket service timer; do
  while read -r UNIT; do
    [[ -n "${UNIT}" ]] || continue
    ! systemctl is-active --quiet "${UNIT}" || continue
    log_warn "Unit [${UNIT}] not active, starting again"
    try 60 systemctl start "${UNIT}"
    systemctl is-active --quiet "${UNIT}" || fail "not active [${UNIT}]"
  done < <(recorded "${KIND}" | startable)
done
if was auditd && ! systemctl is-active --quiet auditd.service; then
  fail "not active [auditd.service]"
fi
BAD=("${UNHEALTHY[@]}")
while read -r ID; do
  [[ -n "${ID}" ]] || continue
  if [[ "$(docker inspect --format '{{.State.Running}}' "${ID}" 2>/dev/null)" != "true" ]]; then
    fail "container not running [${ID}]"
    BAD+=("${ID}")
  fi
done < <(recorded container)
[[ ${#MISSING[@]} -eq 0 ]] || fail "not mounted [${MISSING[*]}]"
[[ "${WRITABLE_ROOT}" == "true" ]] || fail "root read only"
[[ ${#UNHEALTHY[@]} -eq 0 ]] || fail "not healthy [${UNHEALTHY[*]}]"
if [[ ${#STARTING[@]} -gt 0 ]]; then
  log_warn "Still starting [${STARTING[*]}]"
  WARNED+=("still starting ${STARTING[*]}")
fi
if was swap && [[ -z "$(swapon --noheadings --show=NAME 2>/dev/null)" ]]; then
  log_warn "Swap not on"
  WARNED+=("swap not on")
fi
STATUS=0
REASON=ok
if [[ ${#BAD[@]} -gt 0 ]]; then
  STATUS=6
  REASON=unhealthy
elif [[ ${#FAILED[@]} -gt 0 && ${TIMEOUTS} -gt 0 ]]; then
  STATUS=4
  REASON=timeout
elif [[ ${#FAILED[@]} -gt 0 ]]; then
  STATUS=1
  REASON=error
fi
for ITEM in "${FAILED[@]}"; do log_error "Summary, failed [${ITEM}]"; done
for ITEM in "${WARNED[@]}"; do log_warn "Summary, warning [${ITEM}]"; done
if [[ ${STATUS} -eq 0 ]]; then
  rm -f "${STATE}"
  log_info "Host [$(hostname)] awake"
else
  printf 'awoke %s %s\n' "$(date +%s)" "${STATUS}" >>"${STATE}"
  log_error "Host [$(hostname)] not fully awake, record kept at [${STATE}] to retry"
fi
log_info "Log kept at [${LOG_FILE}], took [$(elapsed "${STARTED}")] ms"
RESULT="status=${STATUS} reason=${REASON} mode=${MODE:-none}"
RESULT+=" failed=${#FAILED[@]} warnings=${#WARNED[@]} timeouts=${TIMEOUTS}"
log_info "RESULT awake ${RESULT}"
exit "${STATUS}"
