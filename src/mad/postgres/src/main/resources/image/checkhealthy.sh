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
  /asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" && PGPASSWORD="${POSTGRES_KEY_HASS}" psql -h "${POSTGRES_SERVICE}" -p "${POSTGRES_API_PORT}" -U "${POSTGRES_USER_HASS}" -d "${POSTGRES_DATABASE_HASS}" -c "SELECT 1;" >/dev/null 2>&1 && PGPASSWORD="${POSTGRES_KEY_MLFLOW}" psql -h "${POSTGRES_SERVICE}" -p "${POSTGRES_API_PORT}" -U "${POSTGRES_USER_MLFLOW}" -d "${POSTGRES_DATABASE_MLFLOW}" -c "SELECT 1;" >/dev/null 2>&1
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [postgres] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [postgres] is *NOT* healthy :(" >&2
  exit 1
fi
