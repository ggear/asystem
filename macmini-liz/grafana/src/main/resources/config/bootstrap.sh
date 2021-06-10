#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! nc -z ${GRAFANA_HOST} ${GRAFANA_PORT} >>/dev/null 2>&1; do
  echo "Waiting for grafana to come up ..." && sleep 1
done

if [ -d /bootstrap/grafonnet-lib ]; then
  sleep 5
fi

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
curl -XPUT --silent ${GRAFANA_URL}/api/orgs/1 \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Public Portal"
      }' | jq
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB_V2?orgId=1 | jq -r '.name' | grep InfluxDB_V2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V2",
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
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB_V1?orgId=1 | grep InfluxDB_V1 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V1",
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
if [ $(curl --silent ${GRAFANA_URL}/api/folders/default?orgId=1 | grep default | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/folders?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Default",
          "title": "Default"
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/folders/public_mobile?orgId=1 | grep public_mobile | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/folders?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Mobile",
          "title": "Public _Mobile"
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/folders/public_desktop?orgId=1 | grep public_desktop | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/folders?orgId=1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Desktop",
          "title": "Public_Desktop"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/folders?orgId=1 | jq
if [ -d /bootstrap/grafonnet-lib ]; then
  cd /bootstrap/grafonnet-lib
  find ../dashboards/public -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 >/dev/null && ../grizzly/grr apply $1' sh {} \;
  find ../dashboards/default -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 >/dev/null && ../grizzly/grr apply $1' sh {} \;

fi

curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
if [ $(curl --silent ${GRAFANA_URL}/api/orgs/2 | jq -r '.id' | grep 2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB_V2?orgId=2 | jq -r '.name' | grep InfluxDB_V2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V2",
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
if [ $(curl --silent ${GRAFANA_URL}/api/datasources/name/InfluxDB_V1?orgId=2 | grep InfluxDB_V1 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/datasources?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V1",
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
if [ $(curl --silent ${GRAFANA_URL}/api/folders/private_mobile?orgId=2 | grep private_mobile | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/folders?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Mobile",
          "title": "Private_Mobile"
        }' | jq
fi
if [ $(curl --silent ${GRAFANA_URL}/api/folders/private_desktop?orgId=2 | grep private_desktop | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 > /dev/null && curl -XPOST --silent ${GRAFANA_URL}/api/folders?orgId=2 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Desktop",
          "title": "Private_Desktop"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/folders?orgId=2 | jq
if [ -d /bootstrap/grafonnet-lib ]; then
  cd /bootstrap/grafonnet-lib
  find ../dashboards/private -name dashboard_* -exec sh -c 'curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 >/dev/null && ../grizzly/grr apply $1' sh {} \;
fi

echo "--------------------------------------------------------------------------------"
echo "Grafana bootstrap finished"
echo "--------------------------------------------------------------------------------"
