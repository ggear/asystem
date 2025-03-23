#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

pull_repo "${ROOT_DIR}" "${1}" weewx weewx-core weewx/weewx v${WEEWX_VERSION}
[ $(ls ${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*.whl 2>/dev/null | wc -l) -eq 0 ] && cd ${ROOT_DIR}/../../../.deps/weewx/weewx-core && rm -rf dist && make clean pypi-package
mkdir -p ${ROOT_DIR}/src/main/resources/image/install
cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*.whl ${ROOT_DIR}/src/main/resources/image/install

VERSION=master
pull_repo "${ROOT_DIR}" "${1}" weewx weewx-mqtt matthewwall/weewx-mqtt "${VERSION}"
[ $(ls ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt/weewx-mqtt.zip~ 2>/dev/null | wc -l) -eq 0 ] && cd ${ROOT_DIR}/../../../.deps/weewx && zip -x "weewx-mqtt/.git*" -r weewx-mqtt.zip~ weewx-mqtt && mv ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt.zip~ ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt
mkdir -p ${ROOT_DIR}/src/main/resources/image/install
cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt/weewx-mqtt.zip~ ${ROOT_DIR}/src/main/resources/image/install/weewx-mqtt.zip

VERSION=v3.3.2
pull_repo "${ROOT_DIR}" "${1}" weewx weewx-loopdata chaunceygardiner/weewx-loopdata "${VERSION}"
[ $(ls ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt/weewx-loopdata.zip~ 2>/dev/null | wc -l) -eq 0 ] && cd ${ROOT_DIR}/../../../.deps/weewx && zip -x "weewx-loopdata/.git*" -r weewx-loopdata.zip~ weewx-loopdata && mv ${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata.zip~ ${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata
mkdir -p ${ROOT_DIR}/src/main/resources/image/install
cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-loopdata/weewx-loopdata.zip~ ${ROOT_DIR}/src/main/resources/image/install/weewx-loopdata.zip

VERSION=ggear-skins_seasons
pull_repo "${ROOT_DIR}" "${1}" weewx weewx-core-skins ggear/weewx "${VERSION}"
rm -rf ${ROOT_DIR}/src/main/resources/image/config/skins/Seasons
mkdir -p ${ROOT_DIR}/src/main/resources/image/config/skins
cp -rf ${ROOT_DIR}/../../../.deps/weewx/weewx-core-skins/skins/Seasons ${ROOT_DIR}/src/main/resources/image/config/skins

VERSION=ggear-skins_material
pull_repo "${ROOT_DIR}" "${1}" weewx neowx-material ggear/neowx-material "${VERSION}"
rm -rf ${ROOT_DIR}/src/main/resources/image/config/skins/Material
mkdir -p ${ROOT_DIR}/src/main/resources/image/config/skins
cp -rf ${ROOT_DIR}/../../../.deps/weewx/neowx-material/src ${ROOT_DIR}/src/main/resources/image/config/skins/Material
