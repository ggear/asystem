#!/bin/sh

rm -rf src/main/resources/config/skins
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../asystem-external/weewx/skins/Seasons src/main/resources/config/skins
sed -i '' 's/bottom_label_format = %x %X/bottom_label_format = %d\/%m\/%Y %H:%M/g' src/main/resources/config/skins/Seasons/skin.conf
