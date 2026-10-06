#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

BUILD_TIMEOUT="${BUILD_TIMEOUT:-900}"
if command -v timeout >/dev/null 2>&1; then
	BUILD_TIMEOUT_CMD=(timeout "${BUILD_TIMEOUT}")
elif command -v gtimeout >/dev/null 2>&1; then
	BUILD_TIMEOUT_CMD=(gtimeout "${BUILD_TIMEOUT}")
else
	BUILD_TIMEOUT_CMD=()
fi

if [ -x /opt/homebrew/bin/brew ]; then
	eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
	eval "$(/usr/local/bin/brew shellenv)"
fi
if command -v yarn >/dev/null 2>&1; then YARN_CMD=(yarn); elif command -v corepack >/dev/null 2>&1; then YARN_CMD=(corepack yarn); elif [ -x /opt/homebrew/bin/yarn ]; then YARN_CMD=(/opt/homebrew/bin/yarn); elif [ -x /opt/homebrew/bin/corepack ]; then YARN_CMD=(/opt/homebrew/bin/corepack yarn); elif [ -x /opt/homebrew/bin/npx ]; then YARN_CMD=(/opt/homebrew/bin/npx -y yarn@1.22.22); else echo "No yarn, corepack or npx found" >&2 && exit 127; fi

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "homeassistant-core" "home-assistant/core" "${VERSION}" || exit $?

# NOTES: https://github.com/pkissling/clock-weather-card/releases
VERSION=ggear-patches
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "clock-weather-card" "ggear/clock-weather-card" "${VERSION}" || exit $?
"${BUILD_TIMEOUT_CMD[@]}" "${YARN_CMD[@]}" --cwd "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card" install &&
"${BUILD_TIMEOUT_CMD[@]}" "${YARN_CMD[@]}" --cwd "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card" build || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/clock-weather-card/dist/clock-weather-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/clock-weather-card/clock-weather-card.js" || exit $?

# NOTES: https://github.com/ashtonau/bom-radar-card/releases
VERSION=v1.10.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "bom-radar-card" "ggear/bom-radar-card" "ggear-patches" "https://github.com/ashtonau/bom-radar-card.git" "${VERSION}" || exit $?
"${BUILD_TIMEOUT_CMD[@]}" npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/bom-radar-card" install --no-audit --no-fund || exit $?
"${BUILD_TIMEOUT_CMD[@]}" npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/bom-radar-card" run build || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/bom-radar-card/dist/bom-radar-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/bom-radar-card/bom-radar-card.js" || exit $?

# NOTES: https://github.com/aukedejong/lovelace-windrose-card/releases (upstream tags lag main; track main for latest fixes)
VERSION=main
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "windrose-card" "ggear/windrose-card" "ggear-patches" "https://github.com/aukedejong/lovelace-windrose-card.git" "${VERSION}" || exit $?
"${BUILD_TIMEOUT_CMD[@]}" npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/windrose-card" ci --no-audit --no-fund || exit $?
echo "[windrose-card] running esbuild build"
"${BUILD_TIMEOUT_CMD[@]}" npm --prefix "${ROOT_DIR}/../../../.deps/homeassistant/windrose-card" run esbuild || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/windrose-card/build/windrose-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/windrose-card/windrose-card.js" || exit $?

# NOTES: https://github.com/thomasloven/lovelace-card-mod/releases
VERSION=v4.2.1-202604
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "lovelace-card-mod" "thomasloven/lovelace-card-mod" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/lovelace-card-mod/card-mod.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/card-mod/card-mod.js" || exit $?

# NOTES: https://github.com/thomasloven/lovelace-layout-card/releases
VERSION=v2.4.7
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "lovelace-layout-card" "thomasloven/lovelace-layout-card" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/lovelace-layout-card/layout-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/layout-card/layout-card.js" || exit $?

# NOTES: https://github.com/RomRider/apexcharts-card/releases
VERSION=v2.2.3
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "apexcharts-card" "romrider/apexcharts-card" "${VERSION}" || exit $?
wget -q -O "${ROOT_DIR}/../../../.deps/homeassistant/apexcharts-card-apexcharts-card.js" "https://github.com/RomRider/apexcharts-card/releases/download/${VERSION}/apexcharts-card.js" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/apexcharts-card-apexcharts-card.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/apexcharts-card/apexcharts-card.js" || exit $?

# NOTES: https://github.com/kalkih/mini-graph-card/releases
VERSION=v0.13.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "mini-graph-card" "kalkih/mini-graph-card" "${VERSION}" || exit $?
wget -q -O "${ROOT_DIR}/../../../.deps/homeassistant/mini-graph-card-mini-graph-card-bundle.js" "https://github.com/kalkih/mini-graph-card/releases/download/${VERSION}/mini-graph-card-bundle.js" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/mini-graph-card-mini-graph-card-bundle.js" "${ROOT_DIR}/src/main/resources/data/www/custom_ui/mini-graph-card/mini-graph-card-bundle.js" || exit $?

# NOTES: https://github.com/safepay/ha_bom_australia/releases
VERSION=v1.6.7
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "ha_bom_australia-component" "safepay/ha_bom_australia" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/ha_bom_australia-component/custom_components/ha_bom_australia" "${ROOT_DIR}/src/main/resources/data/custom_components/ha_bom_australia" || exit $?

# NOTES: https://github.com/ggear/willywindforecast-hass-component/tags
VERSION=0.1.3
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "willywindforecast-hass-component" "ggear/willywindforecast-hass-component" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/willywindforecast-hass-component/custom_components/willywindforecast" "${ROOT_DIR}/src/main/resources/data/custom_components/willywindforecast" || exit $?

# NOTES: https://github.com/pnbruckner/ha-sun2/releases
VERSION=3.4.3
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "sun2-component" "pnbruckner/ha-sun2" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/sun2-component/custom_components/sun2" "${ROOT_DIR}/src/main/resources/data/custom_components/sun2" || exit $?

# NOTES: https://github.com/Limych/ha-average/releases
VERSION=2.4.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "average-component" "limych/ha-average" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/average-component/custom_components/average" "${ROOT_DIR}/src/main/resources/data/custom_components/average" || exit $?

# NOTES: https://github.com/basnijholt/adaptive-lighting/releases
VERSION=v1.32.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "adaptive-lighting-component" "basnijholt/adaptive-lighting" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/adaptive-lighting-component/custom_components/adaptive_lighting" "${ROOT_DIR}/src/main/resources/data/custom_components/adaptive_lighting" || exit $?

# NOTES: https://github.com/bramstroker/homeassistant-powercalc/releases
VERSION=v1.26.0
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "powercalc-component" "ggear/homeassistant-powercalc" "ggear-powercalc" "https://github.com/bramstroker/homeassistant-powercalc.git" "${VERSION}" || exit $?
for PATCH_FILE in sonos/move/model.json signify/LCT010/model.json; do
	if [ ! -f "${ROOT_DIR}/../../../.deps/homeassistant/powercalc-component/custom_components/powercalc/custom_data/${PATCH_FILE}" ]; then
		echo "Patched powercalc profile missing [${PATCH_FILE}], refusing to ship unpatched powercalc" >&2
		exit 1
	fi
done
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/powercalc-component/custom_components/powercalc" "${ROOT_DIR}/src/main/resources/data/custom_components/powercalc" || exit $?

# NOTES: https://github.com/home-assistant/core/tree/dev/homeassistant/components/tplink
VERSION=${HOMEASSISTANT_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "homeassistant" "tplink-component" "ggear/homeassistant-core" "ggear-tplink" "https://github.com/home-assistant/core.git" "${VERSION}" || exit $?
if ! grep -qs '"version": "[^"]*ASYSTEM-ggear-tplink"' "${ROOT_DIR}/../../../.deps/homeassistant/tplink-component/homeassistant/components/tplink/manifest.json"; then
	echo "Patched tplink manifest lacks the ASYSTEM-ggear-tplink version, refusing to ship unpatched tplink" >&2
	exit 1
fi
replace_path "${ROOT_DIR}/../../../.deps/homeassistant/tplink-component/homeassistant/components/tplink" "${ROOT_DIR}/src/main/resources/data/custom_components/tplink" || exit $?
