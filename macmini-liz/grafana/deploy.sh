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
find ../../config/dashboards/instance/public -name dashboard_* -exec ../grizzly/grr apply {} \;
find ../../config/dashboards/instance/default -name dashboard_* -exec ../grizzly/grr apply {} \;

echo "---" && echo "Setting up [PRIVATE] organisation"
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
find ../../config/dashboards/instance/private -name dashboard_* -exec ../grizzly/grr apply {} \;