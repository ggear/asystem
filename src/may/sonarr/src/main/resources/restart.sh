#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# ./restart.sh enabled|policy|ready
# The watch is `supervisor serve`, this file holds only the module's hooks.

RESTART_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${RESTART_INTERNAL_ENV}" ] && . "${RESTART_INTERNAL_ENV}"

RESTART_MODULE_NAME="sonarr"
RESTART_ENABLED="${SONARR_RESTART:-off}"

restart_enabled() { [ "${RESTART_ENABLED}" = "on" ]; }

restart_policy() { :; }

restart_ready() { return 0; }

# The engine (`supervisor`) owns the watch and the restart, this snippet owns what must hold first, as hooks each in its
# own bash. A module enrols with <MODULE>_RESTART=on in .env. Optional hooks: restart_policy, restart_ready.
# No hook relies on a variable another set.
#
# restart_policy prints key=value lines:
#   requires=mount:<path> | mounts:all-cifs | tcp:<host>:<port> | mqtt:<host>:<port>:<mqttv31|mqttv311|mqttv5> | healthy:<service>
#   requires_stable=<n>s   how long every requirement must have held, default 60s
#   settle_min=<n>s        when set, the least wait before a late-prerequisite restart in place of the health window, and the least settle after any restart
# restart_ready returns zero when what requires cannot say holds, called once every requirement has held.
#
# RESTART_MODULE_NAME     this module's name
# RESTART_ENABLED         on when .env switches the restart on

restart_policy() {
  echo "requires=mount:/share/10"
  echo "requires=tcp:${SABNZBD_SERVICE_PROD:?}:${SABNZBD_HTTP_PORT:?}"
  echo "requires_stable=15s"
  echo "settle_min=30s"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

case "${1:-}" in
enabled) restart_enabled ;;
policy) restart_policy ;;
ready) restart_ready ;;
*)
  echo "Usage: restart.sh enabled|policy|ready" >&2
  exit 2
  ;;
esac