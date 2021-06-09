#!/bin/bash

. .env
export GOROOT=/usr/local/opt/go/libexec
export GOPATH=${HOME}/.go
export PATH=${GOPATH}/bin:${GOROOT}/bin:$PATH
export GRAFANA_HOST=${GRAFANA_HOST_PROD}
export GRAFANA_PORT=${GRAFANA_PORT}
export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}

./src/main/resources/config/bootstrap.sh

cd src/main/resources/libraries/grizzly
make dev
cd ../grafonnet-lib

echo "---" && echo "Setting up [PUBLIC] organisation"
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/desktop/dashboard_home.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/desktop/dashboards_all.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/mobile/dashboard_home.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/mobile/dashboards_all.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/public/generated/mobile/dashboard_default.jsonnet

echo "---" && echo "Setting up [PRIVATE] organisation"
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/desktop/dashboard_home.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/desktop/dashboards_all.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/mobile/dashboard_home.jsonnet
./../grizzly/grr apply ./../../config/dashboards/instance/private/generated/mobile/dashboards_all.jsonnet
