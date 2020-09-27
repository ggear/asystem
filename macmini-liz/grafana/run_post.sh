#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit
. config/.profile
cd config/grizzly
make dev
curl -i -XPOST --silent -H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: ${GRAFANA_KEY}" "http://localhost:3000/api/datasources" -d '
{
  "name": "influxdb",
  "type": "influxdb",
  "url":"http://192.168.1.10:9999",
  "organisation":"home",
  "token":"${INFLUXDB_TOKEN}",
}'
cd ../grafonnet-lib
GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000 ./../grizzly/grr apply ./../dashboards_all.jsonnet
