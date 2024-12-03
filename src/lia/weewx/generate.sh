#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

pull_repo $(pwd) weewx weewx-core weewx/weewx v${WEEWX_VERSION} ${1}
[ $(ls ${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*.whl 2>/dev/null | wc -l) -eq 0 ] && cd ${ROOT_DIR}/../../../.deps/weewx/weewx-core && rm -rf dist && make pypi-package
mkdir -p ${ROOT_DIR}/src/build/resources
cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx*.whl ${ROOT_DIR}/src/build/resources

VERSION=master
pull_repo $(pwd) weewx weewx-mqtt matthewwall/weewx-mqtt ${VERSION} ${1}
[ $(ls ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt/weewx-mqtt.zip~ 2>/dev/null | wc -l) -eq 0 ] && cd ${ROOT_DIR}/../../../.deps/weewx && zip -x "weewx-mqtt/.git*" -r weewx-mqtt.zip~ weewx-mqtt && mv ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt.zip~ ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt
mkdir -p ${ROOT_DIR}/src/build/resources
cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt/weewx-mqtt.zip~ ${ROOT_DIR}/src/build/resources/weewx-mqtt.zip

VERSION=ggear-skins_seasons
pull_repo $(pwd) weewx weewx-core-skins ggear/weewx ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/skins/Seasons
mkdir -p ${ROOT_DIR}/src/main/resources/config/skins
cp -rf ${ROOT_DIR}/../../../.deps/weewx/weewx-core-skins/skins/Seasons ${ROOT_DIR}/src/main/resources/config/skins

VERSION=ggear-skins_material
pull_repo $(pwd) weewx neowx-material ggear/neowx-material ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/skins/Material
mkdir -p ${ROOT_DIR}/src/main/resources/config/skins
cp -rf ${ROOT_DIR}/../../../.deps/weewx/neowx-material/src ${ROOT_DIR}/src/main/resources/config/skins/Material
