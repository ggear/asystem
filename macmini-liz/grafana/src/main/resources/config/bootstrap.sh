#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! nc -z ${GRAFANA_HOST} ${GRAFANA_PORT} >>/dev/null 2>&1; do
  echo "Waiting for grafana to come up ..." && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

curl -XPUT --silent ${GRAFANA_URL}/api/orgs/1 \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Public Portal"
      }' | jq
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB2Public?orgId=1 | jq -r '.name' | grep InfluxDB2Public | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB2Public",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
          "access": "proxy",
          "isDefault": true,
          "jsonData": {
            "version": "Flux",
            "organization": "'"${INFLUXDB_ORG}"'",
            "defaultBucket": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'"
          },
          "secureJsonData": {
            "token": "'"${INFLUXDB_TOKEN_PUBLIC_V2}"'"
          },
          "secureJsonFields": {
            "token": true
          }
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB1Public?orgId=1 | grep InfluxDB1Public | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB1Public",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
          "access": "proxy",
          "isDefault": false,
          "database": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'",
          "user": "'"${INFLUXDB_USER_PUBLIC}"'",
          "password": "'"${INFLUXDB_TOKEN_PUBLIC_V1}"'"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/datasources?orgId=1 | jq
cd /bootstrap/grafonnet-lib
../grizzly/grr apply ../dashboards//public/generated/desktop/dashboards_all.jsonnet
../grizzly/grr apply ../dashboards//public/generated/mobile/dashboards_all.jsonnet

if [ $(curl --silent ${GRAFANA_URL}/api/orgs/2 | jq -r '.id' | grep 2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi
curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB2Private?orgId=2 | jq -r '.name' | grep InfluxDB2Private | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB2Private",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
          "access": "proxy",
          "isDefault": true,
          "jsonData": {
            "version": "Flux",
            "organization": "'"${INFLUXDB_ORG}"'",
            "defaultBucket": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'"
          },
          "secureJsonData": {
            "token": "'"${INFLUXDB_TOKEN}"'"
          },
          "secureJsonFields": {
            "token": true
          }
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB1Private?orgId=2 | grep InfluxDB1Private | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB1Private",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_PORT}"'",
          "access": "proxy",
          "isDefault": false,
          "database": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'",
          "user": "'"${INFLUXDB_USER_PUBLIC}"'",
          "password": "'"${INFLUXDB_TOKEN}"'"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/datasources?orgId=2 | jq
cd /bootstrap/grafonnet-lib
../grizzly/grr apply ../dashboards//private/generated/desktop/dashboards_all.jsonnet
../grizzly/grr apply ../dashboards//private/generated/mobile/dashboards_all.jsonnet

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap finished"
echo "--------------------------------------------------------------------------------"
