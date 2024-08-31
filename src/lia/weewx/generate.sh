#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

VERSION=v5.1.0
pull_repo $(pwd) weewx weewx-core weewx/weewx ${VERSION} ${1}
(cd ${ROOT_DIR}/../../../.deps/weewx/weewx-core && rm -rf dist/weewx-*.tar.gz && make pypi-package) &&
  mkdir -p ${ROOT_DIR}/src/build/resources &&
  rm ${ROOT_DIR}/src/build/resources/weewx-*.tar.gz &&
  cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-core/dist/weewx-*.tar.gz ${ROOT_DIR}/src/build/resources

VERSION=ggear-weewx-mqtt
pull_repo $(pwd) weewx weewx-mqtt ggear/weewx-mqtt ${VERSION} ${1}
(cd ${ROOT_DIR}/../../../.deps/weewx && zip -x "weewx-mqtt/.git*" -r weewx-mqtt.zip weewx-mqtt) &&
  mkdir -p ${ROOT_DIR}/src/build/resources &&
  cp -nv ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt.zip ${ROOT_DIR}/src/build/resources &&
  rm -rf ${ROOT_DIR}/../../../.deps/weewx/weewx-mqtt.zip

VERSION=ggear-skins_seasons
pull_repo $(pwd) weewx weewx-core-skins ggear/weewx ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/skins/Seasons
mkdir -p ${ROOT_DIR}/src/main/resources/config/skins &&
  cp -rvf ${ROOT_DIR}/../../../.deps/weewx/weewx-core-skins/skins/Seasons ${ROOT_DIR}/src/main/resources/config/skins

VERSION=ggear-skins_material
pull_repo $(pwd) weewx neowx-material ggear/neowx-material ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/skins/Material
mkdir -p ${ROOT_DIR}/src/main/resources/config/skins &&
  cp -rvf ${ROOT_DIR}/../../../.deps/weewx/neowx-material/src ${ROOT_DIR}/src/main/resources/config/skins/Material
