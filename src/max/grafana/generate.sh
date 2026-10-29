#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

pull_repo "${ROOT_DIR}" "${1}" "grafana" "gcx" "grafana/gcx" "v${GRAFANACX_VERSION}" || exit $?

# NOTES: https://github.com/grafana/business-charts/releases
VERSION=7.2.5
if ! grep -qs "\"version\": \"${VERSION}\"" "${ROOT_DIR}/src/main/resources/image/plugins/volkovlabs-echarts-panel/plugin.json"; then
  PLUGIN_ZIP="$(mktemp)"
  trap 'rm -f "${PLUGIN_ZIP}"' EXIT
  curl -sfSL --max-time 300 -o "${PLUGIN_ZIP}" "https://grafana.com/api/plugins/volkovlabs-echarts-panel/versions/${VERSION}/download" || exit $?
  echo "e49f520eef92f391d11c77a94f5503b540451e9e755da9ac5cb3553a8e5db3b5  ${PLUGIN_ZIP}" | shasum -a 256 -c - >/dev/null || exit $?
  rm -rf "${ROOT_DIR}/src/main/resources/image/plugins" && mkdir -p "${ROOT_DIR}/src/main/resources/image/plugins" && unzip -q "${PLUGIN_ZIP}" -d "${ROOT_DIR}/src/main/resources/image/plugins" || exit $?
fi
