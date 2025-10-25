#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
pull_repo "${ROOT_DIR}" "${1}" "sonarr" "sonarr" "sonarr/sonarr" "v${SONARR_VERSION}"
if [ ! -f "${ROOT_DIR}/src/main/resources/image/Sonarr.main.${SONARR_VERSION}.linux-x64.tar.gz" ]; then
  mkdir -p "${ROOT_DIR}/src/main/resources/image"
  rm -rf "${ROOT_DIR}/src/main/resources/image/"*.gz
  curl -fL -o "${ROOT_DIR}/src/main/resources/image/Sonarr.main.${SONARR_VERSION}.linux-x64.tar.gz" "https://github.com/Sonarr/Sonarr/releases/download/v${SONARR_VERSION}/Sonarr.main.${SONARR_VERSION}.linux-x64.tar.gz"
fi
