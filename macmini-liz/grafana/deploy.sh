#!/bin/sh

. .env
export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}
cd src/main/resources/libraries/grizzly
make dev
cd ../grafonnet-lib

echo "---" && echo "Setting up [PUBLIC] organisation"
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/desktop/dashboards_all.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/mobile/dashboards_all.jsonnet

echo "---" && echo "Setting up [PRIVATE] organisation"
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/desktop/dashboards_all.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/mobile/dashboards_all.jsonnet
