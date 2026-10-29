#!/bin/bash

################################################################################
# asleep, quiesce the host so a power cut lands on clean disks, never powers off
#
# Usage
#   asleep [--deep | --shallow] [--keep UNIT]... [--stop CONTAINER]... [--stop-timeout SECONDS] [--quiet] [--dry-run]
#
# Options
#   --deep            stop everything, root and every mount read only (default)
#   --shallow         leave docker, swap, journal and root alone, unmount what no container holds
#   --keep UNIT       spare a host service from the stop, may repeat
#   --stop NAME       stop this container, shallow only, may repeat
#   --stop-timeout    grace seconds per container before it is killed, default 120
#   --quiet           drop DEBUG lines
#   --dry-run         print the steps, change nothing
#
# Exit codes
#   0  ok           every post-condition verified
#   1  error        a post-condition failed, a service still active or a mount still writable
#   2  usage        bad arguments
#   3  precondition not root, or no copy could be staged under /run
#   4  timeout      a step hit its limit and the host ended in the wrong state
#   5  unclean      a container was killed or exited non-zero
#
# Run as root on the host, from a file not a pipe, it re-executes from /run.
# The last line is RESULT asleep status=<code> reason=<ok|error|timeout|unclean>
################################################################################

set -uo pipefail

################################################################################
# Logging
################################################################################
MODE=deep
STOP_TIMEOUT=120
DRY_RUN=false
QUIET=false
RUN_ID="$(date +%s)-$$"
LOG_FILE="${ASLEEP_LOG:-/run/asleep.log}"
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

note() {
  [[ "${DRY_RUN}" == "true" ]] || printf '%s\n' "$*" >>"${STATE}"
  return 0
}
note_all() {
  local kind="$1" item
  shift
  for item in "$@"; do note "${kind} ${item}"; done
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

units() {
  if [[ "$1" == "any" ]]; then
    systemctl list-units --state="$2" --plain --no-legend --no-pager | awk '{print $1}'
  else
    systemctl list-units --type="$1" --state="$2" --plain --no-legend --no-pager | awk '{print $1}'
  fi
}

################################################################################
# Arguments
################################################################################
ARGS=("$@")
KEEP_NAMES=()
STOP_NAMES=()
usage() {
  log_error "Usage, asleep [--deep | --shallow] [--keep UNIT] [--stop CONTAINER] [--quiet] [--dry-run]"
  log_error "Usage, asleep [--stop-timeout SECONDS], options marked [] may repeat or be omitted"
  exit 2
}
while [[ $# -gt 0 ]]; do
  case "$1" in
  -n | --dry-run) DRY_RUN=true ;;
  -q | --quiet) QUIET=true ;;
  --deep) MODE=deep ;;
  --shallow) MODE=shallow ;;
  --keep)
    [[ $# -ge 2 ]] || usage
    KEEP_NAMES+=("$2")
    shift
    ;;
  --stop)
    [[ $# -ge 2 ]] || usage
    STOP_NAMES+=("$2")
    shift
    ;;
  --stop-timeout)
    [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || usage
    STOP_TIMEOUT="$2"
    shift
    ;;
  *) usage ;;
  esac
  shift
done
if [[ ${#STOP_NAMES[@]} -gt 0 && "${MODE}" != "shallow" ]]; then
  log_error "Option [--stop] needs [--shallow], deep stops every container"
  exit 2
fi

################################################################################
# Stage
################################################################################
if [[ "${ASLEEP_STAGED:-}" != "true" ]]; then
  [[ ${EUID} -eq 0 ]] || {
    log_error "Must run as root"
    exit 3
  }
  STAGED="$(mktemp /run/asleep.XXXXXX)" && cp "$0" "${STAGED}" &&
    ASLEEP_STAGED=true exec bash "${STAGED}" "${ARGS[@]}" </dev/null
  log_error "Could not stage a copy under [/run]"
  exit 3
fi
trap '' HUP
trap 'log_debug "Exiting, exit code [$?]"; rm -f "$0"' EXIT
[[ "${DRY_RUN}" == "true" ]] || : >"${LOG_FILE}"

log_info "Starting, host [$(hostname)], mode [${MODE}], dry run [${DRY_RUN}], run [${RUN_ID}]"
log_debug "Script [$(sha256sum "$0" | cut -c1-12)], user [$(id -un)], pid [$$], log [${LOG_FILE}], state [${STATE}]"
log_debug "Keep [${KEEP_NAMES[*]:-}], stop [${STOP_NAMES[*]:-}], stop timeout [${STOP_TIMEOUT}] seconds"

################################################################################
# Docker
################################################################################
section "Docker"
DOCKER_UP=false
RUNNING=()
if has docker && systemctl is-active --quiet docker.service; then
  DOCKER_UP=true
  mapfile -t RUNNING < <(docker ps --format '{{.ID}} {{.Names}}')
fi
log_debug "Docker up [${DOCKER_UP}], containers running [${#RUNNING[@]}]"
if [[ "${MODE}" == "deep" && "${DOCKER_UP}" == "true" && ${#KEEP_NAMES[@]} -gt 0 ]]; then
  for NAME in "${KEEP_NAMES[@]}"; do
    if printf '%s\n' "${RUNNING[@]}" | awk '{print $2}' | grep -qxF "${NAME}"; then
      log_error "Container [${NAME}] cannot be kept, deep stops docker"
      exit 2
    fi
  done
fi

UNCLEAN=()
stop_containers() {
  local id configured seconds code name
  for id in "$@"; do
    name="$(docker inspect --format '{{.Name}}' "${id}" 2>/dev/null)"
    configured="$(docker inspect --format '{{if .Config.StopTimeout}}{{.Config.StopTimeout}}{{end}}' "${id}")"
    seconds="${STOP_TIMEOUT}"
    [[ -z "${configured}" || ${configured} -le ${seconds} ]] || seconds="${configured}"
    log_info "Stopping container [${name#/}], id [${id}], grace [${seconds}] seconds, configured [${configured:-none}]"
    run timeout $((seconds + 30)) docker stop -t "${seconds}" "${id}" &
  done
  wait
  run sync
  [[ "${DRY_RUN}" == "true" ]] && return 0
  for id in "$@"; do
    code="$(docker inspect --format '{{.State.ExitCode}}' "${id}" 2>/dev/null)"
    name="$(docker inspect --format '{{.Name}}' "${id}" 2>/dev/null)"
    if [[ "$(docker inspect --format '{{.State.Running}}' "${id}" 2>/dev/null)" == "true" ]]; then
      fail "container still running [${name#/}]"
      TIMEOUTS=$((TIMEOUTS + 1))
      continue
    fi
    log_debug "Container [${name#/}] finished [$(docker inspect --format '{{.State.FinishedAt}}' "${id}" 2>/dev/null)]"
    log_debug "Container [${name#/}] oom killed [$(docker inspect --format '{{.State.OOMKilled}}' "${id}" 2>/dev/null)]"
    case "${code}" in
    0 | 143) log_info "Container [${name#/}] stopped cleanly, exit code [${code}]" ;;
    *)
      log_warn "Container [${name#/}] not stopped cleanly, exit code [${code}]"
      UNCLEAN+=("${name#/}:${code}")
      ;;
    esac
  done
}

[[ "${DRY_RUN}" == "true" ]] || : >"${STATE}"
note "mode ${MODE}"
snapshot before

################################################################################
# Timers and automounts
################################################################################
section "Timers and automounts"
mapfile -t TIMERS < <(units timer active)
for UNIT in "${TIMERS[@]}"; do log_debug "Timer [${UNIT}] to stop"; done
note_all timer "${TIMERS[@]}"
[[ ${#TIMERS[@]} -eq 0 ]] || try 60 systemctl stop "${TIMERS[@]}"
mapfile -t AUTOMOUNTS < <(units automount active)
for UNIT in "${AUTOMOUNTS[@]}"; do log_debug "Automount [${UNIT}] to stop"; done
note_all automount "${AUTOMOUNTS[@]}"
[[ ${#AUTOMOUNTS[@]} -eq 0 ]] || try 60 systemctl stop "${AUTOMOUNTS[@]}"

################################################################################
# Containers
################################################################################
section "Containers"
RUNNING_AFTER=("${RUNNING[@]}")
if [[ "${DOCKER_UP}" == "true" ]]; then
  if [[ "${MODE}" == "deep" ]]; then
    mapfile -t CONTAINERS < <(printf '%s\n' "${RUNNING[@]}" | awk 'NF {print $1}')
    note docker
    note_all container "${CONTAINERS[@]}"
    [[ ${#CONTAINERS[@]} -eq 0 ]] || stop_containers "${CONTAINERS[@]}"
    try 120 systemctl stop docker.socket docker.service containerd.service
    if [[ "${DRY_RUN}" != "true" ]] && systemctl is-active --quiet docker.service; then
      fail "docker still running"
    fi
    RUNNING_AFTER=()
  elif [[ ${#STOP_NAMES[@]} -gt 0 ]]; then
    STOP_IDS=()
    RUNNING_AFTER=()
    for LINE in "${RUNNING[@]}"; do
      if printf '%s\n' "${STOP_NAMES[@]}" | grep -qxF "${LINE#* }"; then
        STOP_IDS+=("${LINE%% *}")
      else
        log_debug "Container [${LINE#* }] left running"
        RUNNING_AFTER+=("${LINE}")
      fi
    done
    for NAME in "${STOP_NAMES[@]}"; do
      printf '%s\n' "${RUNNING[@]}" | awk '{print $2}' | grep -qxF "${NAME}" || log_warn "Container [${NAME}] not running"
    done
    note_all container "${STOP_IDS[@]}"
    [[ ${#STOP_IDS[@]} -eq 0 ]] || stop_containers "${STOP_IDS[@]}"
  else
    log_debug "Shallow with nothing to stop, containers left running [${#RUNNING[@]}]"
  fi
elif [[ ${#STOP_NAMES[@]} -gt 0 ]]; then
  log_warn "Docker not running, nothing to stop"
fi

################################################################################
# Services
################################################################################
section "Services"
KEEP_UNITS='ssh|sshd|sshd@.*|dbus|dbus-broker|polkit|NetworkManager|networking|wpa_supplicant|chrony|chronyd|ntpsec|ntp'
KEEP_UNITS+='|nut-.*|mbpfan|systemd-.*|getty@.*|serial-getty@.*|user@.*|user-runtime-dir@.*'
[[ "${MODE}" == "deep" ]] || KEEP_UNITS+='|docker|containerd'
for NAME in "${KEEP_NAMES[@]}"; do
  KEEP_UNITS+="|$(printf '%s' "${NAME%.service}" | sed 's/[][\.*^$+?(){}|]/\\&/g')"
done
KEEP="^(${KEEP_UNITS})\\.service\$"
for UNIT in $(units service running | grep -E "${KEEP}"); do log_debug "Service [${UNIT}] kept, in the keep list"; done
mapfile -t CANDIDATES < <(units service running | grep -Ev "${KEEP}" | grep -vx 'auditd.service')
SERVICES=()
for UNIT in "${CANDIDATES[@]}"; do
  if [[ "$(systemctl show --property=Transient --value "${UNIT}")" == "yes" ]]; then
    log_info "Service [${UNIT}] kept, transient and cannot be restarted by name"
  else
    log_debug "Service [${UNIT}] to stop"
    SERVICES+=("${UNIT}")
  fi
done
mapfile -t ACTIVE_SOCKETS < <(units socket active)
SOCKETS=()
for UNIT in "${SERVICES[@]}"; do
  if printf '%s\n' "${ACTIVE_SOCKETS[@]}" | grep -qxF "${UNIT%.service}.socket"; then
    log_debug "Socket [${UNIT%.service}.socket] to stop, it triggers [${UNIT}]"
    SOCKETS+=("${UNIT%.service}.socket")
  fi
done
note_all socket "${SOCKETS[@]}"
note_all service "${SERVICES[@]}"
[[ ${#SOCKETS[@]} -eq 0 && ${#SERVICES[@]} -eq 0 ]] || try 300 systemctl stop "${SOCKETS[@]}" "${SERVICES[@]}"
if has service && systemctl is-active --quiet auditd.service && [[ " ${KEEP_NAMES[*]:-} " != *" auditd "* ]]; then
  note auditd
  log_debug "Service [auditd.service] to stop, it refuses systemctl stop so service is used"
  try 30 service auditd stop
  if [[ "${DRY_RUN}" != "true" ]] && systemctl is-active --quiet auditd.service; then
    fail "still active [auditd.service]"
  fi
fi
if [[ "${DRY_RUN}" != "true" ]]; then
  for PASS in 1 2; do
    STILL=()
    for UNIT in "${SERVICES[@]}" "${SOCKETS[@]}" "${TIMERS[@]}" "${AUTOMOUNTS[@]}"; do
      ! systemctl is-active --quiet "${UNIT}" || STILL+=("${UNIT}")
    done
    log_debug "Verify pass [${PASS}], still active [${STILL[*]:-}]"
    [[ ${#STILL[@]} -eq 0 ]] && break
    if ((PASS == 1)); then try 120 systemctl stop "${STILL[@]}"; fi
  done
  for UNIT in "${STILL[@]}"; do
    fail "still active [${UNIT}]"
  done
fi

################################################################################
# Journal
################################################################################
section "Journal"
if [[ "${MODE}" == "deep" ]]; then
  try 30 journalctl --sync
  try 30 journalctl --relinquish-var
else
  log_debug "Journal left alone, mode [shallow]"
fi

################################################################################
# Swap
################################################################################
section "Swap"
if [[ "${MODE}" == "deep" && -n "$(swapon --noheadings --show=NAME 2>/dev/null)" ]]; then
  SWAP_USED_KB="$(awk '/^SwapTotal:/ {t=$2} /^SwapFree:/ {f=$2} END {print t-f}' /proc/meminfo)"
  MEM_AVAILABLE_KB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  log_debug "Swap used [${SWAP_USED_KB}] kB, memory available [${MEM_AVAILABLE_KB}] kB"
  if ((MEM_AVAILABLE_KB > SWAP_USED_KB * 2)); then
    note swap
    try 120 swapoff -a
  else
    log_warn "Swap kept, used [${SWAP_USED_KB}] kB would not fit in available [${MEM_AVAILABLE_KB}] kB"
  fi
else
  log_debug "Swap left alone, mode [${MODE}]"
fi

################################################################################
# Held mounts
################################################################################
section "Held mounts"
PIN_SOURCES=()
if [[ "${MODE}" == "shallow" && "${DOCKER_UP}" == "true" ]]; then
  DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null)"
  [[ -z "${DOCKER_ROOT}" ]] || PIN_SOURCES+=("docker|${DOCKER_ROOT}")
  for LINE in "${RUNNING_AFTER[@]}"; do
    while read -r SOURCE; do
      [[ -z "${SOURCE}" ]] || PIN_SOURCES+=("${LINE#* }|${SOURCE}")
    done < <(docker inspect --format '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}' "${LINE%% *}")
  done
fi
for PIN in "${PIN_SOURCES[@]}"; do log_debug "Holder [${PIN%%|*}], source [${PIN#*|}]"; done
held_by() {
  local target="$1" entry source
  for entry in "${PIN_SOURCES[@]}"; do
    source="${entry#*|}"
    if [[ "${source}" == "/" || "${source}" == "${target}" ||
      "${source}" == "${target}"/* || "${target}" == "${source}"/* ]]; then
      printf '%s' "${entry%%|*}"
      return 0
    fi
  done
  return 1
}
HELD=()

################################################################################
# Unmount
################################################################################
section "Unmount"
run sync
mapfile -t TARGETS < <(
  findmnt --fstab --noheadings --raw --output TARGET,FSTYPE |
    awk '$1 ~ /^\// && $1 != "/" && $2 != "swap" {print length($1), $1}' |
    sort -rn | cut -d' ' -f2-
)
log_debug "Unmount order [${TARGETS[*]:-}]"
for TARGET in "${TARGETS[@]}"; do
  if ! mountpoint -q "${TARGET}"; then
    log_debug "Mount [${TARGET}] skipped, not mounted"
    continue
  fi
  if HOLDER="$(held_by "${TARGET}")"; then
    HELD+=("${TARGET}|${HOLDER}")
    log_info "Mount [${TARGET}] kept, held by [${HOLDER}]"
    continue
  fi
  FSTYPE="$(findmnt --noheadings --output FSTYPE --target "${TARGET}" | tail -1)"
  log_debug "Mount [${TARGET}] to unmount, type [${FSTYPE}]"
  if attempt 30 umount "${TARGET}"; then
    note mount "${TARGET}"
    log_info "Mount [${TARGET}] unmounted"
    continue
  fi
  case "${FSTYPE}" in
  cifs | nfs | nfs4 | fuse.*)
    if attempt 30 umount -l "${TARGET}"; then
      note mount "${TARGET}"
      log_info "Mount [${TARGET}] unmounted lazily"
    else
      log_warn "Mount [${TARGET}] could not be unmounted lazily"
    fi
    ;;
  *)
    if attempt 30 mount -o remount,ro "${TARGET}"; then
      note remount "${TARGET}"
      log_info "Mount [${TARGET}] busy, remounted read only"
    else
      log_warn "Mount [${TARGET}] could not be remounted read only"
    fi
    ;;
  esac
done

################################################################################
# Root filesystem
################################################################################
section "Root filesystem"
if [[ "${MODE}" == "shallow" ]]; then
  log_info "Root left writable, mode [shallow]"
elif attempt 30 mount -o remount,ro /; then
  note remount /
  log_info "Root remounted read only"
else
  fail "root left writable"
  if has fuser; then fuser -vm / 2>&1 | log_out || true; fi
fi

################################################################################
# Devices
################################################################################
section "Devices"
while read -r DISK; do
  if [[ "${DISK}" != sd* ]]; then
    log_debug "Disk [${DISK}] skipped, not an sd device"
    continue
  fi
  if lsblk --raw --noheadings --output MOUNTPOINTS "/dev/${DISK}" | grep -q .; then
    log_debug "Disk [${DISK}] skipped, has mounts"
    continue
  fi
  log_info "Disk [${DISK}] to flush and detach, model [$(lsblk --nodeps --noheadings --output MODEL "/dev/${DISK}" | xargs)]"
  try 30 blockdev --flushbufs "/dev/${DISK}"
  if has hdparm; then try 30 hdparm -y "/dev/${DISK}"; fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    log_info "+ detach [/dev/${DISK}]"
  elif echo 1 >"/sys/block/${DISK}/device/delete"; then
    log_info "Disk [${DISK}] detached"
  else
    log_warn "Disk [${DISK}] could not be detached"
    WARNED+=("detach /dev/${DISK}")
  fi
done < <(lsblk --nodeps --noheadings --output NAME,TYPE | awk '$2 == "disk" {print $1}')

################################################################################
# Verdict
################################################################################
section "Verdict"
run sync
UNEXPECTED=()
while read -r TARGET; do
  if [[ "${MODE}" == "shallow" ]]; then
    [[ "${TARGET}" == "/" ]] && continue
    printf '%s\n' "${HELD[@]:-}" | cut -d'|' -f1 | grep -qxF "${TARGET}" && continue
  fi
  UNEXPECTED+=("${TARGET}")
done < <(findmnt --raw --noheadings --output TARGET,SOURCE,OPTIONS | awk '$2 ~ /^\/dev\// && $3 ~ /(^|,)rw(,|$)/ {print $1}')
if [[ ${#UNEXPECTED[@]} -gt 0 ]]; then
  fail "still writable [${UNEXPECTED[*]}]"
fi
if [[ ${#UNCLEAN[@]} -gt 0 ]]; then
  fail "containers not stopped cleanly [${UNCLEAN[*]}]"
fi
snapshot after
if [[ "${DRY_RUN}" == "true" ]]; then
  log_info "Dry run complete, nothing changed"
  exit 0
fi
STATUS=0
REASON=ok
if [[ ${#UNCLEAN[@]} -gt 0 ]]; then
  STATUS=5
  REASON=unclean
elif [[ ${#FAILED[@]} -gt 0 && ${TIMEOUTS} -gt 0 ]]; then
  STATUS=4
  REASON=timeout
elif [[ ${#FAILED[@]} -gt 0 ]]; then
  STATUS=1
  REASON=error
fi
note "complete $(date +%s) status ${STATUS} reason ${REASON}"
for ITEM in "${FAILED[@]}"; do log_error "Summary, failed [${ITEM}]"; done
for ITEM in "${WARNED[@]}"; do log_warn "Summary, warning [${ITEM}]"; done
if [[ ${STATUS} -ne 0 ]]; then
  log_error "Host [$(hostname)] not fully quiesced, mode [${MODE}]"
elif [[ "${MODE}" == "shallow" ]]; then
  log_info "Host [$(hostname)] reduced for power loss, writable by design [/ ${HELD[*]//|/ by }]"
else
  log_info "Host [$(hostname)] ready for power loss"
fi
log_info "Log kept at [${LOG_FILE}], took [$(elapsed "${STARTED}")] ms"
RESULT="status=${STATUS} reason=${REASON} mode=${MODE}"
RESULT+=" failed=${#FAILED[@]} warnings=${#WARNED[@]} timeouts=${TIMEOUTS}"
log_info "RESULT asleep ${RESULT}"
exit "${STATUS}"
