#!/bin/bash

. ../../../generate.sh

pull_repo $(pwd) weewx weewx-core ggear/weewx v4.6.2-ggear ${1}
pull_repo $(pwd) weewx neowx-material ggear/neowx-material 1.11-ggear ${1}
rm -rf src/main/resources/config/skins
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../.deps/weewx/weewx-core/skins/Seasons src/main/resources/config/skins &&
  cp -rvf ../../../.deps/weewx/neowx-material/src src/main/resources/config/skins/Material
