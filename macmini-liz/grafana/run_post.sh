#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
. ./.env
cd config/grizzly
GOPATH=$SERVICE_HOME/.go make dev
if [ $(curl --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_IP}:${GRAFANA_PORT}/api/datasources/name/InfluxDB2" | grep "InfluxDB2" | wc -l) -eq 0 ]; then
  curl -XPOST --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_IP}:${GRAFANA_PORT}/api/datasources" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB2",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_IP}:${INFLUXDB_PORT}"'",
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
fi
if [ $(curl --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_IP}:${GRAFANA_PORT}/api/datasources/name/InfluxDB1" | grep "InfluxDB1" | wc -l) -eq 0 ]; then
  curl -XPOST --silent "http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_IP}:${GRAFANA_PORT}/api/datasources" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB1",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_IP}:${INFLUXDB_PORT}"'",
          "access": "proxy",
          "isDefault": false,
          "database": "hosts",
          "user": "influxdb",
          "password": "'"${INFLUXDB_TOKEN}"'"
        }'
fi
cd ../grafonnet-lib
GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000 ./../grizzly/grr apply ./../dashboards/template/generated/dashboards_all.jsonnet
