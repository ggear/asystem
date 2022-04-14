#!/bin/bash

. $(pwd)/../../generate.sh

pull_repo $(pwd) homeassistant bom-weather-card davidfw1960/bom-weather-card 0.90a
rm -rf src/main/resources/config/www/custom_ui/bom-weather-card
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons &&
  unzip ../../.deps/homeassistant/bom-weather-card/bom_icons.zip -d src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons &&
  unzip ../../.deps/homeassistant/bom-weather-card/weather_icons.zip -d src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons
mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card &&
  cp -rvf ../../.deps/homeassistant/bom-weather-card/bom-weather-card.js src/main/resources/config/www/custom_ui/bom-weather-card &&
  sed -i '' 's/\/local\/icons/\/local\/custom_ui\/bom-weather-card\/icons/g' src/main/resources/config/www/custom_ui/bom-weather-card/bom-weather-card.js
for FILE in illuminance.yaml lovelace.yaml weather.yaml; do
  mkdir -p src/main/resources/config/www/custom_ui/bom-weather-card &&
    cp -rvf ../../.deps/homeassistant/bom-weather-card/${FILE} src/main/resources/config/www/custom_ui/bom-weather-card &&
    sed -i '' 's/kariong/darlington_forecast/g' src/main/resources/config/www/custom_ui/bom-weather-card/${FILE} &&
    sed -i '' 's/gosford/gooseberry_hill/g' src/main/resources/config/www/custom_ui/bom-weather-card/${FILE}
done

pull_repo $(pwd) homeassistant bom-radar-card makin-things/bom-radar-card v1.5.0
rm -rf src/main/resources/config/www/custom_ui/bom-radar-card
mkdir -p src/main/resources/config/www/custom_ui/bom-radar-card &&
  cp -rvf ../../.deps/homeassistant/bom-radar-card/dist/* src/main/resources/config/www/custom_ui/bom-radar-card &&
  sed -i '' 's/\/local\/community/\/local\/custom_ui/g' src/main/resources/config/www/custom_ui/bom-radar-card/bom-radar-card.js &&
  wget -q -O src/main/resources/config/www/custom_ui/bom-radar-card/leaflet.js.map https://unpkg.com/leaflet@1.7.1/dist/leaflet.js.map

pull_repo $(pwd) homeassistant lovelace-layout-card thomasloven/lovelace-layout-card 2.4.1
rm -rf src/main/resources/config/www/custom_ui/layout-card
mkdir -p src/main/resources/config/www/custom_ui/layout-card &&
  cp -rvf ../../.deps/homeassistant/lovelace-layout-card/layout-card.js src/main/resources/config/www/custom_ui/layout-card

pull_repo $(pwd) homeassistant apexcharts-card romrider/apexcharts-card v1.10.0
rm -rf src/main/resources/config/www/custom_ui/apexcharts-card
mkdir -p src/main/resources/config/www/custom_ui/apexcharts-card &&
  wget -q -O src/main/resources/config/www/custom_ui/apexcharts-card/apexcharts-card.js https://github.com/RomRider/apexcharts-card/releases/download/v1.10.0/apexcharts-card.js

pull_repo $(pwd) homeassistant mini-graph-card kalkih/mini-graph-card v0.10.0
rm -rf src/main/resources/config/www/custom_ui/mini-graph-card
mkdir -p src/main/resources/config/www/custom_ui/mini-graph-card &&
  wget -q -O src/main/resources/config/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js https://github.com/kalkih/mini-graph-card/releases/download/v0.10.0/mini-graph-card-bundle.js

pull_repo $(pwd) homeassistant sun2-component pnbruckner/ha-sun2 2.0.2
rm -rf src/main/resources/config/custom_components/sun2
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/sun2-component/custom_components/sun2 src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant average-component limych/ha-average 2.1.0
rm -rf src/main/resources/config/custom_components/average
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/average-component/custom_components/average src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant bureau_of_meteorology-component bremor/bureau_of_meteorology 0.10.3
rm -rf src/main/resources/config/custom_components/bureau_of_meteorology
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/bureau_of_meteorology-component/custom_components/bureau_of_meteorology src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant powercalc-component bramstroker/homeassistant-powercalc v0.18.4
rm -rf src/main/resources/config/custom_components/powercalc
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/powercalc-component/custom_components/powercalc src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant adaptive-lighting-component basnijholt/adaptive-lighting 1.0.15
rm -rf src/main/resources/config/custom_components/adaptive_lighting
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/adaptive-lighting-component/custom_components/adaptive_lighting src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant senseme-component mikelawrence/senseme-hacs v2.2.5
rm -rf src/main/resources/config/custom_components/senseme
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/senseme-component/custom_components/senseme src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant withings-component ggear/homeassistant-core ggear-withings
rm -rf src/main/resources/config/custom_components/withings
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/withings-component/homeassistant/components/withings src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant tplink-component ggear/homeassistant-core ggear-tplink
rm -rf src/main/resources/config/custom_components/tplink
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/tplink-component/homeassistant/components/tplink src/main/resources/config/custom_components

pull_repo $(pwd) homeassistant homekit-component ggear/homeassistant-core ggear-homekit
rm -rf src/main/resources/config/custom_components/homekit
mkdir -p src/main/resources/config/custom_components &&
  cp -rvf ../../.deps/homeassistant/homekit-component/homeassistant/components/homekit src/main/resources/config/custom_components
