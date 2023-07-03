#!/bin/bash

. ../../../generate.sh

VERSION=v4.10.2
pull_repo $(pwd) weewx weewx-core weewx/weewx ${VERSION} ${1}
(cd ../../../.deps/weewx/weewx-core && make src-package)
mkdir -p src/build/resources &&
  cp -nv ../../../.deps/weewx/weewx-core/dist/weewx-*.tar.gz src/build/resources

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
