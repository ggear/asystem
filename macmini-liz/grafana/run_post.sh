#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit
. config/.profile
cd config/grizzly
make dev
curl -i -XPOST --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@localhost:3000/api/datasources" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json"
  -d '{
        "name": "InfluxDB",
        "type": "influxdb",
        "url": "http://macmini-liz:8086",
        "access": "proxy",
        "jsonData": {
          "version": "Flux",
          "organization": "home",
          "defaultBucket": "asystem"
        },
        "secureJsonData": {
          "token": "${INFLUXDB_TOKEN}"
        },
        "secureJsonFields": {
          "token": true
        }
      }'
cd ../grafonnet-lib
GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000 ./../grizzly/grr apply ./../dashboards_all.jsonnet
