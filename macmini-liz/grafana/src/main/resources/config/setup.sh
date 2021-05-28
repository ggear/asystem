#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Grafana custom setup initialising ..."
echo "--------------------------------------------------------------------------------"

apk add curl==7.77.0-r0 jq==1.6-r1 git==2.26.3-r0 make==4.3-r0 musl-dev==1.1.24-r10 go==1.13.15-r0

export GOROOT=/usr/lib/go
export GOPATH=/go
export PATH=/go/bin:$PATH
mkdir -p ${GOPATH}/src ${GOPATH}/bin
go get -u github.com/Masterminds/glide/...
cd /bootstrap/grizzly
make dev
cd /bootstrap/grafonnet-lib

while ! nc -z ${GRAFANA_HOST} ${GRAFANA_PORT} >>/dev/null 2>&1; do
  echo "Waiting for grafana to come up ..." && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Grafana custom setup starting ..."
echo "--------------------------------------------------------------------------------"

curl -XPUT --silent ${GRAFANA_URL}/api/orgs/1 \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Public Portal"
      }' | jq
if [ $(curl --silent ${GRAFANA_URL}/api/orgs/2 | jq -r '.id' | grep 2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/orgs | jq

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

/bootstrap/grizzly/grr apply ../dashboards/template/generated/dashboards_all.jsonnet

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
            "token": "'"${INFLUXDB_TOKEN_PUBLIC_V2}"'"
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
          "password": "'"${INFLUXDB_TOKEN_PUBLIC_V1}"'"
        }' | jq
fi
curl --silent ${GRAFANA_URL}/api/datasources?orgId=2 | jq

/bootstrap/grizzly/grr apply ../dashboards/template/generated/dashboards_all.jsonnet

# TODO: Delete
sleep 10000

echo "--------------------------------------------------------------------------------"
echo "Grafana custom setup finished"
echo "--------------------------------------------------------------------------------"
