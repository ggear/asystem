#!/usr/bin/env bash

# Runs one stage of a backup run, from the supervisor probe or by hand, the same path both sides.
#
#   backup.sh <primary|secondary|tertiary> [start|stop] [run-id]
#
# Stages of one run must share a run id - a stage reads what the earlier stages of that run recorded.
# start heartbeats a status document and exits on the stage result, detaching only on a hand run,
# never under the probe, which owns the redirection and reads that status. stop is idempotent and
# never unmounts a share. The stage contract is in backup/lib.sh, and each stage holds one of its own:
#
# primary   never reads a data directory or knows a backup format, the module's own backup.sh owns
#           both, and a service is enrolled by shipping one.
# secondary is additive and never deletes, mounts the share on demand and never unmounts it, and
#           delegates thinning to the service, falling back to backup_thin for one shipping none.
# tertiary  is server hosts only, mirrors each locally-owned share whole - media and service homes,
#           not just backups - guarded on both mounts, and brings the disk up and down around itself.

# shellcheck source-path=SCRIPTDIR
set -uo pipefail

BACKUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_STAGE="${1:-}"
BACKUP_PHASE="${2:-start}"
BACKUP_STAGE_FILE="${BACKUP_ROOT}/backup/${BACKUP_STAGE}.sh"

if [ ! -r "${BACKUP_STAGE_FILE}" ] || { [ "${BACKUP_PHASE}" != "start" ] && [ "${BACKUP_PHASE}" != "stop" ]; }; then
  echo "Usage: ${0} <primary|secondary|tertiary> [start|stop] [run-id]" >&2
  exit 2
fi

BACKUP_RUN_ID="${3:-${BACKUP_RUN_ID:-$(date +%Y-%m-%d_%H-%M-%S)}}"
BACKUP_TRIGGER="${BACKUP_TRIGGER:-manual}"
[ -n "${BACKUP_RUN_ID_PASSED:-}" ] && BACKUP_TRIGGER="scheduled"
BACKUP_INSTALL_ROOT="${BACKUP_INSTALL_ROOT:-/var/lib/asystem/install}"
BACKUP_HOME_ROOT="${BACKUP_HOME_ROOT:-/home/asystem}"
BACKUP_RUN_PATH="${BACKUP_RUN_PATH:-${BACKUP_HOME_ROOT}/supervisor/backup/${BACKUP_RUN_ID}}"
BACKUP_STAGE_DIR="${BACKUP_RUN_PATH}/stage/${BACKUP_STAGE}"
BACKUP_LOG="${BACKUP_STAGE_DIR}/output.log"
BACKUP_CONFIG="${BACKUP_INSTALL_ROOT}/supervisor/latest/image/config.json"

mkdir -p "${BACKUP_STAGE_DIR}"

BACKUP_ENV="${BACKUP_INSTALL_ROOT}/supervisor/latest/.env"
# shellcheck disable=SC1090
if [ -f "${BACKUP_ENV}" ]; then set -a; . "${BACKUP_ENV}"; set +a; fi
BACKUP_HOST="${SUPERVISOR_HOST:-$(hostname)}"

# shellcheck source=backup/lib.sh
. "${BACKUP_ROOT}/backup/lib.sh"
# shellcheck source=/dev/null
. "${BACKUP_STAGE_FILE}"

BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-$(backup_config '.asystem.backup.timeout_hours' 3)}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-$(backup_config '.asystem.backup.keep_daily' 7)}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-$(backup_config '.asystem.backup.keep_weekly' 4)}"
BACKUP_KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-$(backup_config '.asystem.backup.keep_monthly' 12)}"
BACKUP_HEARTBEAT_REFRESH="${BACKUP_HEARTBEAT_REFRESH:-600}"
BACKUP_HEARTBEAT_GRACE="${BACKUP_HEARTBEAT_GRACE:-3600}"
BACKUP_HEARTBEAT_PID=""

BACKUP_USAGE=0
BACKUP_FILES=0
BACKUP_FILES_HELD=0
BACKUP_FILES_CREATED=0
BACKUP_FILES_DELETED=0
BACKUP_SIZE=0
BACKUP_SIZE_HELD=0
BACKUP_SENT=0

if [ "${BACKUP_PHASE}" = "stop" ]; then
  exec >>"${BACKUP_LOG}" 2>&1
  stage_stop || true
  exit 0
fi

if [ -z "${BACKUP_DETACHED:-}" ] && [ -z "${BACKUP_RUN_ID_PASSED:-}" ] && { [ -t 1 ] || [ "${BACKUP_TIMEOUT_HOURS}" = "0" ]; }; then
  export BACKUP_DETACHED=1
  nohup "$0" "${BACKUP_STAGE}" start "${BACKUP_RUN_ID}" >>"${BACKUP_LOG}" 2>&1 &
  disown
  echo "[${BACKUP_STAGE}] detached, following ${BACKUP_LOG}"
  exit 0
fi
[ -n "${BACKUP_RUN_ID_PASSED:-}" ] || exec > >(tee -a "${BACKUP_LOG}") 2>&1

BACKUP_STARTED="$(date +%s)"
trap 'stage_stop || true; backup_settle; exit 143' TERM INT
backup_document "running" false "${BACKUP_STARTED}" "$(( BACKUP_STARTED + BACKUP_HEARTBEAT_GRACE ))"
backup_heartbeat &
BACKUP_HEARTBEAT_PID=$!

if stage_start; then
  backup_settle
  backup_document "complete" true "${BACKUP_STARTED}"
  exit 0
fi
backup_settle
backup_document "failed" false "${BACKUP_STARTED}"
exit 1
