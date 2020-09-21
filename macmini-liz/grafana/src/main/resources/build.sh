#!/bin/sh

. ./config/.profile

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000
export DASHBOARD_ASYSTEM_UID=0fcqnVOGz

cd ./grizzly
make dev
./grr get ${DASHBOARD_ASYSTEM_UID}

cd ../grafonnet-lib
./../grizzly/grr apply ./../monitor.jsonnet
