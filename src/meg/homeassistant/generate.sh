#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

pull_repo "${ROOT_DIR}" "${1}" homeassistant homeassistant-core home-assistant/core "${HOMEASSISTANT_VERSION}"

# Notes: https://github.com/DavidFW1960/bom-weather-card/releases
VERSION=0.90a
pull_repo "${ROOT_DIR}" "${1}" homeassistant bom-weather-card davidfw1960/bom-weather-card "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/icons/bom_icons"
unzip "${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/bom_icons.zip" -d "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/icons/bom_icons"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/icons/weather_icons"
unzip "${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/weather_icons.zip" -d "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/icons/weather_icons"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/bom-weather-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card"
sed -i '' 's/\/local\/icons/\/local\/custom_ui\/bom-weather-card\/icons/g' "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/bom-weather-card.js"
for FILE in illuminance.yaml lovelace.yaml weather.yaml; do
  mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card"
  cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/bom-weather-card/${FILE}" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card"
  sed -i '' 's/kariong/darlington_forecast/g' "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/${FILE}"
  sed -i '' 's/gosford/darlington/g' "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-weather-card/${FILE}"
done

# Notes: https://github.com/Makin-Things/bom-radar-card/releases
VERSION=v3.0.2
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "bom-radar-card" "Makin-Things/bom-radar-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/bom-radar-card/dist/"* "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card"
sed -i '' 's/\/local\/community/\/local\/custom_ui/g' "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card/bom-radar-card.js"
wget -q -O "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card/leaflet.js.map" "https://unpkg.com/leaflet@1.9.2/dist/leaflet.js.map"

# Notes: https://github.com/thomasloven/lovelace-layout-card/releases
VERSION=v2.4.5
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "lovelace-layout-card" "thomasloven/lovelace-layout-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/lovelace-layout-card/layout-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"

# Notes: https://github.com/RomRider/apexcharts-card/releases
VERSION=v2.1.2
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "apexcharts-card" "romrider/apexcharts-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card"
wget -q -O "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card/apexcharts-card.js" "https://github.com/RomRider/apexcharts-card/releases/download/${VERSION}/apexcharts-card.js"

# Notes: https://github.com/kalkih/mini-graph-card/releases
VERSION=v0.12.1
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "mini-graph-card" "kalkih/mini-graph-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card"
wget -q -O "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js" "https://github.com/kalkih/mini-graph-card/releases/download/${VERSION}/mini-graph-card-bundle.js"

# Notes: https://github.com/pnbruckner/ha-sun2/releases
VERSION=3.3.5
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "sun2-component" "pnbruckner/ha-sun2" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/sun2"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/sun2-component/custom_components/sun2" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/Limych/ha-average/releases
VERSION=dev
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "average-component" "limych/ha-average" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/average"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/average-component/custom_components/average" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/bremor/bureau_of_meteorology/releases
VERSION=1.3.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "bureau_of_meteorology-component" "bremor/bureau_of_meteorology" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/bureau_of_meteorology"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/bureau_of_meteorology-component/custom_components/bureau_of_meteorology" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/basnijholt/adaptive-lighting/releases
VERSION=v1.25.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "adaptive-lighting-component" "basnijholt/adaptive-lighting" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/adaptive_lighting"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/adaptive-lighting-component/custom_components/adaptive_lighting" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/bramstroker/homeassistant-powercalc/releases
VERSION=v1.17.11
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "powercalc-component" "ggear/homeassistant-powercalc" "ggear-powercalc" "https://github.com/bramstroker/homeassistant-powercalc.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/powercalc"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/powercalc-component/custom_components/powercalc" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/home-assistant/core/tree/dev/homeassistant/components/influxdb
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "influxdb-component" "ggear/homeassistant-core" "ggear-influxdb" "https://github.com/home-assistant/core.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/influxdb"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/influxdb-component/homeassistant/components/influxdb" "${ROOT_DIR}/src/main/resources/data/custom_components"

# Notes: https://github.com/home-assistant/core/tree/dev/homeassistant/components/tplink
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "tplink-component" "ggear/homeassistant-core" "ggear-tplink" "https://github.com/home-assistant/core.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/tplink"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/tplink-component/homeassistant/components/tplink" "${ROOT_DIR}/src/main/resources/data/custom_components"
