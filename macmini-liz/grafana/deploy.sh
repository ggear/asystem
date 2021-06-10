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
find ../../config/dashboards/instance/public -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 >/dev/null && ../grizzly/grr apply $1' sh {} \;
find ../../config/dashboards/instance/default -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 >/dev/null && ../grizzly/grr apply $1' sh {} \;

echo "---" && echo "Setting up [PRIVATE] organisation"
find ../../config/dashboards/instance/private -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 >/dev/null && ../grizzly/grr apply $1' sh {} \;
