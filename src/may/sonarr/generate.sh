#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${SONARR_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "sonarr" "sonarr" "sonarr/sonarr" "v${VERSION}" "" "" "True" || exit $?
rm -rf "${ROOT_DIR}/src/main/resources/image/"*.gz || exit $?
