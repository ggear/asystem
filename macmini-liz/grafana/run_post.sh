#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit
. ./.env
. ./config/.profile
cd config/grizzly
GOPATH=$SERVICE_HOME/.go make dev
curl -i -XPOST --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@localhost:3000/api/datasources" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "InfluxDB2",
        "type": "influxdb",
        "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
        "access": "proxy",
        "isDefault": true,
        "jsonData": {
          "version": "Flux",
          "organization": "home",
          "defaultBucket": "asystem"
        },
        "secureJsonData": {
          "token": "'"${INFLUXDB_TOKEN}"'"
        },
        "secureJsonFields": {
          "token": true
        }
      }'
curl -i -XPOST --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@localhost:3000/api/datasources" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "InfluxDB1",
        "type": "influxdb",
        "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
        "access": "proxy",
        "isDefault": false,
        "database": "hosts",
        "user": "influxdb",
        "password": "'"${INFLUXDB_TOKEN}"'"
      }'
cd ../grafonnet-lib
GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000 ./../grizzly/grr apply ./../dashboards_all.jsonnet
