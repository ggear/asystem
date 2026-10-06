#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${WEEWX_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "weewx" "weewx-core" "weewx/weewx" "v${VERSION}" || exit $?
if command -v poetry >/dev/null 2>&1; then POETRY_DIR="$(dirname "$(command -v poetry)")"; elif [ -x /opt/homebrew/bin/poetry ]; then POETRY_DIR="/opt/homebrew/bin"; elif [ -x /usr/local/bin/poetry ]; then POETRY_DIR="/usr/local/bin"; else echo "No poetry found" >&2 && exit 127; fi
if ! compgen -G "${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*${VERSION}*.whl" >/dev/null; then
  (cd "${ROOT_DIR}/../../../.deps/weewx/weewx-core" && rm -rf dist && PATH="${POETRY_DIR}:${PATH}" make clean pypi-package) || exit $?
fi
WHEEL="$(compgen -G "${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*${VERSION}*.whl" | head -n 1)"
replace_path "${WHEEL}" "${ROOT_DIR}/src/main/resources/image/install/$(basename "${WHEEL}")" || exit $?
find "${ROOT_DIR}/src/main/resources/image/install" -type f ! -name "weewx*${VERSION}*whl" ! -name "weewx-*.zip" -exec rm {} \; || exit $?

# NOTES: https://github.com/matthewwall/weewx-mqtt/commits/master
VERSION=master
pull_repo "${ROOT_DIR}" "${1}" "weewx" "weewx-mqtt" "matthewwall/weewx-mqtt" "${VERSION}" || exit $?
ZIP_CACHE="${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt-$(git -C "${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt" rev-parse HEAD).zip"
if [ ! -s "${ZIP_CACHE}" ]; then
  rm -f "${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt-"*.zip || exit $?
  git -C "${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt" archive --format=zip --prefix=weewx-mqtt/ -o "${ZIP_CACHE}" HEAD -- . ':(exclude,glob)**/.git*' || exit $?
fi
replace_path "${ZIP_CACHE}" "${ROOT_DIR}/src/main/resources/image/install/weewx-mqtt.zip" || exit $?

# NOTES: https://github.com/chaunceygardiner/weewx-loopdata/releases
VERSION=v7.5.2
pull_repo "${ROOT_DIR}" "${1}" "weewx" "weewx-loopdata" "chaunceygardiner/weewx-loopdata" "${VERSION}" || exit $?
ZIP_CACHE="${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata-$(git -C "${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata" rev-parse HEAD).zip"
if [ ! -s "${ZIP_CACHE}" ]; then
  rm -f "${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata-"*.zip || exit $?
  git -C "${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata" archive --format=zip --prefix=weewx-loopdata/ -o "${ZIP_CACHE}" HEAD -- . ':(exclude,glob)**/.git*' || exit $?
fi
replace_path "${ZIP_CACHE}" "${ROOT_DIR}/src/main/resources/image/install/weewx-loopdata.zip" || exit $?

# NOTES: https://github.com/weewx/weewx/releases
VERSION=ggear-skins_seasons
pull_repo "${ROOT_DIR}" "${1}" "weewx" "weewx-core-skins" "ggear/weewx" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/weewx/weewx-core-skins/skins/Seasons" "${ROOT_DIR}/src/main/resources/image/config/skins/Seasons" || exit $?

# NOTES: https://github.com/neoground/neowx-material/releases
VERSION=ggear-skins_material
pull_repo "${ROOT_DIR}" "${1}" "weewx" "neowx-material" "ggear/neowx-material" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/weewx/neowx-material/src" "${ROOT_DIR}/src/main/resources/image/config/skins/Material" || exit $?
