# shellcheck shell=bash

asystem_locked() {
  local module="${1}" parent="${2}" wait="${3:-300}" file
  [ "${ASYSTEM_LOCK_HELD:-}" = "${module}" ] && return 0
  command -v flock >/dev/null 2>&1 || return 0
  file="${parent}/.lock"
  mkdir -p "${parent}" 2>/dev/null || return 0
  exec 9>"${file}" || return 0
  flock -w "${wait}" 9 || {
    echo "Another actor holds the lock for [${module}] at [${file}], giving up after [${wait}] seconds" >&2
    return 1
  }
  export ASYSTEM_LOCK_HELD="${module}"
}
