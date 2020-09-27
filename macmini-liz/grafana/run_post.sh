#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit


. config/.profile

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000
export DASHBOARD_ASYSTEM_UID=0fcqnVOGz

cd config/grizzly
make dev

cd ../grafonnet-lib
./../grizzly/grr apply ./../dashboards_all.jsonnet
