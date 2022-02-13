#!/bin/sh

rm -rf src/main/resources/config/skins
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../asystem-external/weewx/weewx-core/skins/Seasons src/main/resources/config/skins &&
  cp -rvf ../../../asystem-external/weewx/neowx-material/src src/main/resources/config/skins/Material &&
  cp -rvf ../../../asystem-external/weewx/weewx-responsive-skin/Responsive src/main/resources/config/skins
