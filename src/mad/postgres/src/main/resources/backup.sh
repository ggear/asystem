#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# ./backup.sh [--full | --accept=<run>]
# The run is `supervisor backup run`, this file holds only the module's hooks. A variable set in .env wins.
#
# BACKUP_SOURCE_PATH      data path backed up, defaulting to this module's own
# BACKUP_SKIP_HOURS       skip when the newest backup is younger than this, zero never skips
# BACKUP_SERVICE_RESTART  start the service after the copy, false when the caller does
# BACKUP_TIMEOUT_HOURS    budget before abandoning a backup waiting on its service
# BACKUP_FORCE_FULL       true takes a full backup, set by --full
# BACKUP_SHRINK_PERCENT   fall in total marking a run regressed, zero disables, POSTGRES_BACKUP_SHRINK_PERCENT overrides

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
[ -f "${BACKUP_INTERNAL_ENV}" ] && . "${BACKUP_INTERNAL_ENV}"

BACKUP_MODULE_NAME="postgres"
BACKUP_SOURCE_PATH="${BACKUP_SOURCE_PATH:-${SERVICE_DATA_DIR:-/home/asystem/postgres/latest}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${BACKUP_SOURCE_PATH}")"
BACKUP_SOURCE_VERSION="$(basename "${BACKUP_INTERNAL_SOURCE_DIR}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${BACKUP_INTERNAL_SOURCE_DIR}")/backup"
BACKUP_RUN_TIMESTAMP="${BACKUP_RUN_TIMESTAMP:-$(date +"%Y-%m-%d_%H-%M-%S")}"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_VERSIONED_NONE="unversioned"
BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}"
BACKUP_FORCE_FULL="${BACKUP_FORCE_FULL:-false}"
BACKUP_SERVICE_RESTART="${BACKUP_SERVICE_RESTART:-true}"
BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS:-5}"
BACKUP_SHRINK_PERCENT="${BACKUP_SHRINK_PERCENT:-${POSTGRES_BACKUP_SHRINK_PERCENT:-20}}"
BACKUP_TARGET_PATH=""
BACKUP_NO_EXCLUDES=()

backup_module() {
  "${BACKUP_SUPERVISOR:-/asystem/bin/supervisor}" backup "${1}" "${BACKUP_MODULE_NAME}" --source "${BACKUP_INTERNAL_SOURCE_DIR}" --run "${BACKUP_RUN_TIMESTAMP}" --state "${BACKUP_STATE_DIR:-}" "${@:2}"
}

backup_target() {
  BACKUP_TARGET_PATH="$(backup_module target "${1:-}" "${2:-}")" || return 1
}

backup_files() {
  local -n backup_files_includes="${2}"
  local -n backup_files_excludes="${3:-BACKUP_NO_EXCLUDES}"
  local arguments=() entry live="POSTGRES_BACKUP_LIVE"
  for entry in "${backup_files_includes[@]}"; do arguments+=("--include=${entry}"); done
  for entry in "${backup_files_excludes[@]}"; do arguments+=("--exclude=${entry}"); done
  backup_module files --root "${1:-}" --live "${!live:-}" "${arguments[@]}" || return 1
  BACKUP_TARGET_PATH="$(cat "${BACKUP_STATE_DIR}/target")"
}

backup_parent() { backup_module parent --run "${1:-${BACKUP_RUN_TIMESTAMP}}"; }

backup_epoch() { "${BACKUP_SUPERVISOR:-/asystem/bin/supervisor}" backup epoch "${1:-}"; }

backup_written() {
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}

backup_interrupted() { :; }

backup_completed() { :; }

# The engine (`supervisor backup run`) owns the run, this snippet owns the backup, as hooks each in its own bash.
# Define backup_written, naming the target with backup_target or backup_files and writing "${BACKUP_TARGET_PATH}.tmp".
# Optional hooks: backup_interrupted, backup_completed, backup_pruned_store, backup_versioned.
# No hook relies on a variable another set, own state is prefixed with the module name, .env values expand as "${VAR:?}".
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's data path
# BACKUP_SOURCE_VERSION   the version being backed up
# BACKUP_TARGET_PATH      this run's artefact path, set by backup_target
# BACKUP_RUN_TIMESTAMP    this run's timestamp
# BACKUP_FULL_SUFFIX      suffix of a full backup
# BACKUP_DELTA_SUFFIX     suffix of a delta backup, which needs a full one before it
# BACKUP_VERSIONED_NONE   what backup_versioned prints when a restore needs no software version
# BACKUP_SKIP_HOURS       skip when the newest backup is younger than this, zero never skips

POSTGRES_BACKUP_SKIPPED=(
  "wrangle"
)
POSTGRES_BACKUP_TRANSIENT=(
  "hass:public.event_data"
  "hass:public.events"
  "hass:public.state_attributes"
  "hass:public.states"
  "hass:public.statistics_short_term"
)

backup_versioned() {
  docker exec --user root "${BACKUP_MODULE_NAME}" psql -U postgres -Atc \
    "SELECT current_setting('server_version_num')::int / 10000 || '-' || extversion FROM pg_extension WHERE extname = 'timescaledb'"
}

backup_written() {
  local databases database skipped table excluded
  backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
  mapfile -t databases < <(docker exec --user root "${BACKUP_MODULE_NAME}" \
    psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname")
  if [ "${#databases[@]}" -eq 0 ]; then
    echo "Listed no databases in [${BACKUP_MODULE_NAME}]" >&2
    return 1
  fi
  {
    docker exec --user root "${BACKUP_MODULE_NAME}" pg_dumpall -U postgres --globals-only || exit 1
    for database in "${databases[@]}"; do
      skipped="false"
      for table in "${POSTGRES_BACKUP_SKIPPED[@]}"; do
        [ "${table}" = "${database}" ] && skipped="true"
      done
      if [ "${skipped}" = "true" ]; then
        echo "Skipped database [${database}], it is rebuilt rather than restored" >&2
        continue
      fi
      excluded=()
      for table in "${POSTGRES_BACKUP_TRANSIENT[@]}"; do
        [ "${table%%:*}" = "${database}" ] && excluded+=("--exclude-table-data=${table#*:}")
      done
      case "${database}" in
      postgres | template1)
        printf '\\connect %s\n\n' "${database}"
        docker exec --user root "${BACKUP_MODULE_NAME}" pg_dump -U postgres "${excluded[@]}" "${database}" || exit 1
        ;;
      *)
        docker exec --user root "${BACKUP_MODULE_NAME}" pg_dump -U postgres --create "${excluded[@]}" "${database}" || exit 1
        ;;
      esac
    done
  } | gzip >"${BACKUP_TARGET_PATH}.tmp"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0

BACKUP_INTERNAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"

backup_supervised() {
  local container image seconds=$((BACKUP_TIMEOUT_HOURS * 3600 + 7200))
  if [ -x /asystem/bin/supervisor ]; then
    exec /asystem/bin/supervisor backup "$@"
  fi
  container="$(timeout 30 docker ps --filter name=^/supervisor$ --filter status=running --format '{{.Names}}')"
  if [ -n "${container}" ]; then
    exec timeout "${seconds}" docker exec supervisor /asystem/bin/supervisor backup "$@"
  fi
  image="$(timeout 30 docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^supervisor:' | sort -V | tail -n 1)"
  [ -n "${image}" ] || { echo "No supervisor container is running and no supervisor image is installed, cannot run the backup" >&2; exit 1; }
  exec timeout "${seconds}" docker run --rm --init --entrypoint /asystem/bin/supervisor \
    --volume /home/asystem:/home/asystem --volume /var/lib/asystem/install:/var/lib/asystem/install:ro --volume /var/run/docker.sock:/var/run/docker.sock \
    "${image}" backup "$@"
}

case "${1:-}" in
--accept=*)
  backup_supervised accept "${BACKUP_MODULE_NAME}" "${1#--accept=}" --source "${BACKUP_INTERNAL_SOURCE_DIR}"
  ;;
--full)
  BACKUP_FORCE_FULL="true"
  BACKUP_SKIP_HOURS=0
  shift
  ;;
esac

BACKUP_INTERNAL_ARGUMENTS=(--source "${BACKUP_INTERNAL_SOURCE_DIR}" --script "${BACKUP_INTERNAL_SCRIPT}" --skip-period "${BACKUP_SKIP_HOURS}h" --timeout-period "${BACKUP_TIMEOUT_HOURS}h" --shrink-percent "${BACKUP_SHRINK_PERCENT}")
[ "${BACKUP_SERVICE_RESTART}" = "true" ] || BACKUP_INTERNAL_ARGUMENTS+=(--no-restart)
[ "${BACKUP_FORCE_FULL}" = "true" ] && BACKUP_INTERNAL_ARGUMENTS+=(--force-full)
[ -n "${BACKUP_LOCK_SECONDS:-}" ] && BACKUP_INTERNAL_ARGUMENTS+=(--lock-period "${BACKUP_LOCK_SECONDS}s")

backup_supervised run "${BACKUP_MODULE_NAME}" "${BACKUP_INTERNAL_ARGUMENTS[@]}"