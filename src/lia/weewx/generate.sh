#!/bin/bash

. ../../../generate.sh

VERSION=v5.0.2
pull_repo $(pwd) weewx weewx-core weewx/weewx ${VERSION} ${1}
rm -rf src/build/resources/*.deb &&
  wget -q -O src/build/resources/weewx-${VERSION}.deb http://weewx.com/downloads/released_versions/python3-weewx_$(echo ${VERSION} | sed 's/^v//g')-1_all.deb

VERSION=ggear-skins_seasons
pull_repo $(pwd) weewx weewx-core-skins ggear/weewx ${VERSION} ${1}
rm -rf src/main/resources/config/skins/Seasons
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../.deps/weewx/weewx-core-skins/skins/Seasons src/main/resources/config/skins

VERSION=ggear-skins_material
pull_repo $(pwd) weewx neowx-material ggear/neowx-material ${VERSION} ${1}
rm -rf src/main/resources/config/skins/Material
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../.deps/weewx/neowx-material/src src/main/resources/config/skins/Material
