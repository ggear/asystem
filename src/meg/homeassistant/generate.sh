#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

VERSION=0.90a
pull_repo $(pwd) homeassistant bom-weather-card davidfw1960/bom-weather-card ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons &&
  unzip  ${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/bom_icons.zip -d ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/icons/bom_icons
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons &&
  unzip  ${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/weather_icons.zip -d ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/icons/weather_icons
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/bom-weather-card.js ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card &&
  sed -i '' 's/\/local\/icons/\/local\/custom_ui\/bom-weather-card\/icons/g' ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/bom-weather-card.js
for FILE in illuminance.yaml lovelace.yaml weather.yaml; do
  mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card &&
    cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/${FILE} ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card &&
    sed -i '' 's/kariong/darlington_forecast/g' ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/${FILE} &&
    sed -i '' 's/gosford/darlington/g' ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-weather-card/${FILE}
done

VERSION=v3.0.2
pull_repo $(pwd) homeassistant bom-radar-card makin-things/bom-radar-card ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-radar-card
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-radar-card &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/bom-radar-card/dist/* ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-radar-card &&
  sed -i '' 's/\/local\/community/\/local\/custom_ui/g' ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-radar-card/bom-radar-card.js &&
  wget -q -O ${ROOT_DIR}/src/main/resources/config/www/custom_ui/bom-radar-card/leaflet.js.map https://unpkg.com/leaflet@1.9.2/dist/leaflet.js.map

VERSION=v2.4.5
pull_repo $(pwd) homeassistant lovelace-layout-card thomasloven/lovelace-layout-card ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/www/custom_ui/layout-card
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/layout-card &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/lovelace-layout-card/layout-card.js ${ROOT_DIR}/src/main/resources/config/www/custom_ui/layout-card

VERSION=v2.1.2
pull_repo $(pwd) homeassistant apexcharts-card romrider/apexcharts-card ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/www/custom_ui/apexcharts-card
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/apexcharts-card &&
  wget -q -O ${ROOT_DIR}/src/main/resources/config/www/custom_ui/apexcharts-card/apexcharts-card.js https://github.com/RomRider/apexcharts-card/releases/download/${VERSION}/apexcharts-card.js

VERSION=v0.12.1
pull_repo $(pwd) homeassistant mini-graph-card kalkih/mini-graph-card ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/www/custom_ui/mini-graph-card
mkdir -p ${ROOT_DIR}/src/main/resources/config/www/custom_ui/mini-graph-card &&
  wget -q -O ${ROOT_DIR}/src/main/resources/config/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js https://github.com/kalkih/mini-graph-card/releases/download/${VERSION}/mini-graph-card-bundle.js

VERSION=3.4.3
pull_repo $(pwd) homeassistant variables-component Wibias/hass-variables ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/variable
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/variables-component/custom_components/variable ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=3.3.2
pull_repo $(pwd) homeassistant sun2-component pnbruckner/ha-sun2 ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/sun2
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/sun2-component/custom_components/sun2 ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=dev
pull_repo $(pwd) homeassistant average-component limych/ha-average ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/average
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/average-component/custom_components/average ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=1.3.2
pull_repo $(pwd) homeassistant bureau_of_meteorology-component bremor/bureau_of_meteorology ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/bureau_of_meteorology
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/bureau_of_meteorology-component/custom_components/bureau_of_meteorology ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=1.22.0
pull_repo $(pwd) homeassistant adaptive-lighting-component basnijholt/adaptive-lighting ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/adaptive_lighting
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/adaptive-lighting-component/custom_components/adaptive_lighting ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=ggear-powercalc
pull_repo $(pwd) homeassistant powercalc-component ggear/powercalc ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/powercalc
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/powercalc-component/custom_components/powercalc ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=ggear-influxdb
pull_repo $(pwd) homeassistant influxdb-component ggear/homeassistant-core ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/influxdb
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/influxdb-component/homeassistant/components/influxdb ${ROOT_DIR}/src/main/resources/config/custom_components

VERSION=ggear-tplink
pull_repo $(pwd) homeassistant tplink-component ggear/homeassistant-core ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/custom_components/tplink
mkdir -p ${ROOT_DIR}/src/main/resources/config/custom_components &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/homeassistant/tplink-component/homeassistant/components/tplink ${ROOT_DIR}/src/main/resources/config/custom_components
