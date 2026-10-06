#!/usr/bin/env bash

set -eo pipefail

DASHBOARDS_HOME="/asystem/mnt/dashboards"

gcx() {
  env -u GRAFANA_TOKEN GCX_AGENT_MODE=false GRAFANA_SERVER="http://${GRAFANA_SERVICE}:${GRAFANA_HTTP_PORT}" GRAFANA_ORG_ID=1 \
    GRAFANA_USER="${GRAFANA_USER}" GRAFANA_PASSWORD="${GRAFANA_TOKEN}" gcx --no-color "$@"
}

echo "Pushing folders and dashboards ..."
gcx resources push \
  -p "${DASHBOARDS_HOME}/folders" \
  -p "${DASHBOARDS_HOME}/generated" \
  -p "${DASHBOARDS_HOME}/custom" \
  --omit-manager-fields --on-error abort

echo "Pushing preferences ..."
gcx api "/apis/preferences.grafana.app/v1/namespaces/default/preferences/namespace" \
  -X PUT -H "Content-Type: application/yaml" -d "@${DASHBOARDS_HOME}/config/preferences.yaml" >/dev/null

echo "Deleting dashboards no longer declared ..."
DECLARED="$(find "${DASHBOARDS_HOME}/generated" "${DASHBOARDS_HOME}/custom" -name '*.yaml' -exec basename {} .yaml \;)"
SERVED="$(gcx resources get dashboards -o json | jq -r '.items[].metadata.name')"
for DASHBOARD in ${SERVED}; do
  if ! grep -Fxq "${DASHBOARD}" <<<"${DECLARED}"; then
    gcx resources delete "dashboards/${DASHBOARD}"
  fi
done

curl -sf "${GRAFANA_URL}/api/admin/stats" | jq
