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
  /asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" && mariadb -uroot -p"${MARIADB_ROOT_PASSWORD}" -h "${MARIADB_SERVICE}" -P "${MARIADB_API_PORT}" -e "SELECT 1;" >/dev/null 2>&1
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [mariadb] is executing :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [mariadb] is *NOT* executing :(" >&2
  exit 1
fi
