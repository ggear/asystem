#!/bin/sh

rm -rf src/main/resources/config/skins
mkdir -p src/main/resources/config/skins &&
  cp -rvf ../../../asystem-external/weewx/skins/Seasons src/main/resources/config/skins
sed -i '' 's/anti_alias = 1/anti_alias = 5/g' src/main/resources/config/skins/Seasons/skin.conf
sed -i '' 's/image_width = 500/image_width = 750/g' src/main/resources/config/skins/Seasons/skin.conf
sed -i '' 's/image_height = 180/image_height = 270/g' src/main/resources/config/skins/Seasons/skin.conf
sed -i '' 's/width: 500px; \/\* should match the image width in skin.conf \*\//width: 750px;/g' src/main/resources/config/skins/Seasons/seasons.css
sed -i '' 's/bottom_label_format = %x %X/bottom_label_format = %d\/%m\/%Y %H:%M/g' src/main/resources/config/skins/Seasons/skin.conf
