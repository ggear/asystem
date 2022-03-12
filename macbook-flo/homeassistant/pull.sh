#!/bin/sh

rm -rf src/main/resources/config/www/custom_ui/bom-weather-card
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons &&
  unzip ../../../asystem-external/homeassistant/bom-weather-card/bom_icons.zip -d src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons &&
  unzip ../../../asystem-external/homeassistant/bom-weather-card/weather_icons.zip -d src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card &&
  cp -rvf ../../../asystem-external/homeassistant/bom-weather-card/bom-weather-card.js src/main/resources/config/www/custom_ui/bom-weather-card &&
  sed -i '' 's/\/local\/icons/\/local\/custom_ui\/bom-weather-card\/icons/g' src/main/resources/config/www/custom_ui/bom-weather-card/bom-weather-card.js
for FILE in illuminance.yaml lovelace.yaml weather.yaml; do
  mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card &&
    cp -rvf ../../../asystem-external/homeassistant/bom-weather-card/${FILE} src/main/resources/config/www/custom_ui/bom-weather-card &&
    sed -i '' 's/kariong/darlington_forecast/g' src/main/resources/config/www/custom_ui/bom-weather-card/${FILE} &&
    sed -i '' 's/gosford/gooseberry_hill/g' src/main/resources/config/www/custom_ui/bom-weather-card/${FILE}
done

rm -rf src/main/resources/config/www/custom_ui/bom-radar-card
mkdir -p src/main/resources/config/www/custom_ui/bom-radar-card &&
  cp -rvf ../../../asystem-external/homeassistant/bom-radar-card/dist/* src/main/resources/config/www/custom_ui/bom-radar-card &&
  sed -i '' 's/\/local\/community/\/local\/custom_ui/g' src/main/resources/config/www/custom_ui/bom-radar-card/bom-radar-card.js &&
  wget -q -O src/main/resources/config/www/custom_ui/bom-radar-card/leaflet.js.map https://unpkg.com/leaflet@1.7.1/dist/leaflet.js.map

rm -rf src/main/resources/config/www/custom_ui/layout-card
mkdir -p src/main/resources/config/www/custom_ui/layout-card &&
  cp -rvf ../../../asystem-external/homeassistant/lovelace-layout-card/layout-card.js src/main/resources/config/www/custom_ui/layout-card

rm -rf src/main/resources/config/www/custom_ui/apexcharts-card
mkdir -p src/main/resources/config/www/custom_ui/apexcharts-card &&
  wget -q -O src/main/resources/config/www/custom_ui/apexcharts-card/apexcharts-card.js https://github.com/RomRider/apexcharts-card/releases/download/v1.10.0/apexcharts-card.js

rm -rf src/main/resources/config/www/custom_ui/mini-graph-card
mkdir -p src/main/resources/config/www/custom_ui/mini-graph-card &&
  wget -q -O src/main/resources/config/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js https://github.com/kalkih/mini-graph-card/releases/download/v0.10.0/mini-graph-card-bundle.js

rm -rf src/main/resources/config/custom_components/sun2
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/ha-sun2/custom_components/sun2 src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/average
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/ha-average/custom_components/average src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/bureau_of_meteorology
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/bureau_of_meteorology/custom_components/bureau_of_meteorology src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/unifiprotect
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/unifiprotect/custom_components/unifiprotect src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/withings
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/core-withings/homeassistant/components/withings src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/senseme
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/senseme/custom_components/senseme src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/sonos
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/core-sonos/homeassistant/components/sonos src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/tplink
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/core-tplink/homeassistant/components/tplink src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/powercalc
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/powercalc/custom_components/powercalc src/main/resources/config/custom_components

rm -rf src/main/resources/config/custom_components/adaptive_lighting
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../../asystem-external/homeassistant/adaptive-lighting/custom_components/adaptive_lighting src/main/resources/config/custom_components
