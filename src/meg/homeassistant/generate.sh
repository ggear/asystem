#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

pull_repo "${ROOT_DIR}" "${1}" homeassistant homeassistant-core home-assistant/core "${HOMEASSISTANT_VERSION}"

# NOTES: https://github.com/pkissling/clock-weather-card/releases
VERSION=v2.9.2
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "clock-weather-card" "ggear/clock-weather-card" "ggear-patches" "https://github.com/pkissling/clock-weather-card.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/clock-weather-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/clock-weather-card"
yarn --cwd "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card" install --frozen-lockfile
yarn --cwd "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card" build
cp "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card/dist/clock-weather-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/clock-weather-card/clock-weather-card.js"

# NOTES: https://github.com/Makin-Things/weather-radar-card/releases
VERSION=v2.1.1
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "weather-radar-card" "ggear/weather-radar-card" "ggear-patches" "https://github.com/Makin-Things/weather-radar-card.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/weather-radar-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/weather-radar-card"
npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/weather-radar-card" install
rm -rf "${ROOT_DIR}/../../../.deps/homeassistant/weather-radar-card/node_modules/rollup-plugin-typescript2/node_modules/tslib"
npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/weather-radar-card" run build
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/weather-radar-card/dist/"* "${ROOT_DIR}/src/main/resources/data/www/custom_ui/weather-radar-card"
sed -i '' 's/\/local\/community/\/local\/custom_ui/g' "${ROOT_DIR}/src/main/resources/data/www/custom_ui/weather-radar-card/weather-radar-card.js"

# NOTES: https://github.com/thomasloven/lovelace-card-mod/releases
VERSION=v4.2.1
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "lovelace-card-mod" "thomasloven/lovelace-card-mod" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/card-mod"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/card-mod"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/lovelace-card-mod/card-mod.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/card-mod"

# NOTES: https://github.com/thomasloven/lovelace-layout-card/releases
VERSION=v2.4.7
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "lovelace-layout-card" "thomasloven/lovelace-layout-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/lovelace-layout-card/layout-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card"

# NOTES: https://github.com/RomRider/apexcharts-card/releases
VERSION=v2.2.3
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "apexcharts-card" "romrider/apexcharts-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card"
wget -q -O "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card/apexcharts-card.js" "https://github.com/RomRider/apexcharts-card/releases/download/${VERSION}/apexcharts-card.js"

# NOTES: https://github.com/kalkih/mini-graph-card/releases
VERSION=v0.13.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "mini-graph-card" "kalkih/mini-graph-card" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card"
mkdir -p "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card"
wget -q -O "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js" "https://github.com/kalkih/mini-graph-card/releases/download/${VERSION}/mini-graph-card-bundle.js"

# NOTES: https://github.com/safepay/ha_bom_australia/releases
VERSION=1.6.2
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "ha_bom_australia-component" "safepay/ha_bom_australia" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/ha_bom_australia"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/ha_bom_australia-component/custom_components/ha_bom_australia" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/ggear/willywindforecast-hass-component.git
VERSION=0.1.2
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "willywindforecast-hass-component" "ggear/willywindforecast-hass-component" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/willywindforecast"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/willywindforecast-hass-component/custom_components/willywindforecast" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/pnbruckner/ha-sun2/releases
VERSION=3.4.3
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "sun2-component" "pnbruckner/ha-sun2" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/sun2"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/sun2-component/custom_components/sun2" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/Limych/ha-average/releases
VERSION=2.4.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "average-component" "limych/ha-average" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/average"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/average-component/custom_components/average" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/basnijholt/adaptive-lighting/releases
VERSION=v1.30.1
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "adaptive-lighting-component" "basnijholt/adaptive-lighting" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/adaptive_lighting"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/adaptive-lighting-component/custom_components/adaptive_lighting" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/bramstroker/homeassistant-powercalc/releases
VERSION=v1.20.9
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "powercalc-component" "ggear/homeassistant-powercalc" "ggear-powercalc" "https://github.com/bramstroker/homeassistant-powercalc.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/powercalc"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/powercalc-component/custom_components/powercalc" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/home-assistant/core/tree/dev/homeassistant/components/influxdb
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "influxdb-component" "ggear/homeassistant-core" "ggear-influxdb" "https://github.com/home-assistant/core.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/influxdb"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/influxdb-component/homeassistant/components/influxdb" "${ROOT_DIR}/src/main/resources/data/custom_components"

# NOTES: https://github.com/home-assistant/core/tree/dev/homeassistant/components/tplink
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "tplink-component" "ggear/homeassistant-core" "ggear-tplink" "https://github.com/home-assistant/core.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/data/custom_components/tplink"
mkdir -p "${ROOT_DIR}/src/main/resources/data/custom_components"
cp -rvf "${ROOT_DIR}/../../../.deps/homeassistant/tplink-component/homeassistant/components/tplink" "${ROOT_DIR}/src/main/resources/data/custom_components"
