#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${GCX_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "grafana" "gcx" "grafana/gcx" "v${VERSION}" || exit $?

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${BUSINESS_CHARTS_VERSION}
PLUGIN_DIR="${ROOT_DIR}/src/main/resources/image/plugins"
if ! grep -qs "\"version\": \"${VERSION}\"" "${PLUGIN_DIR}/volkovlabs-echarts-panel/plugin.json"; then
  PLUGIN_ZIP="$(mktemp)"
  trap 'rm -f "${PLUGIN_ZIP}"' EXIT
  curl -sfSL --max-time 300 -o "${PLUGIN_ZIP}" "https://grafana.com/api/plugins/volkovlabs-echarts-panel/versions/${VERSION}/download" || exit $?
  echo "${BUSINESS_CHARTS_SHA256}  ${PLUGIN_ZIP}" | shasum -a 256 -c - >/dev/null || exit $?
  rm -rf "${PLUGIN_DIR}" && mkdir -p "${PLUGIN_DIR}" && unzip -q "${PLUGIN_ZIP}" -d "${PLUGIN_DIR}" || exit $?
fi
