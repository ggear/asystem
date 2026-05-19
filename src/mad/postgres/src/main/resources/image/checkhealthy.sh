#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

POSITIONAL_ARGS=()
HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    HEALTHCHECK_VERBOSE=true
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-v|--verbose] [-h|--help] [alive]"
    exit 2
    ;;
  *)
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  esac
done

if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -x
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

shopt -s expand_aliases

if
  timeout "${ASYSTEM_HEALTHCHECK_TIMEOUT_SECONDS:-30}" bash -c 'until /asystem/etc/checkexecuting.sh "$@" && PGHOST="${POSTGRES_SERVICE}" PGPORT="${POSTGRES_API_PORT}" PGPASSWORD="${POSTGRES_KEY_HASS}" PGUSER="${POSTGRES_USER_HASS}" PGDATABASE="${POSTGRES_DATABASE_HASS}" psql -qAt -c "SELECT 1" >/dev/null 2>&1 && PGHOST="${POSTGRES_SERVICE}" PGPORT="${POSTGRES_API_PORT}" PGPASSWORD="${POSTGRES_KEY_MLFLOW}" PGUSER="${POSTGRES_USER_MLFLOW}" PGDATABASE="${POSTGRES_DATABASE_MLFLOW}" psql -qAt -c "SELECT 1" >/dev/null 2>&1 && PGHOST="${POSTGRES_SERVICE}" PGPORT="${POSTGRES_API_PORT}" PGPASSWORD="${POSTGRES_KEY_WRANGLE}" PGUSER="${POSTGRES_USER_WRANGLE}" PGDATABASE="${POSTGRES_DATABASE_WRANGLE}" psql -qAt -c "SELECT 1" >/dev/null 2>&1 do sleep "${ASYSTEM_HEALTHCHECK_INTERVAL_SECONDS:-1}"; done' _ "${POSITIONAL_ARGS[@]}" || ( echo "Health check timed out after ${ASYSTEM_HEALTHCHECK_TIMEOUT_SECONDS:-30}s" >&2; false )
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [postgres] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [postgres] is *NOT* healthy :(" >&2
  exit 1
fi
