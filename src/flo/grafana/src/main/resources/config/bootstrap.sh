#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

LIBRARIES_HOME=${LIBRARIES_HOME:-"/bootstrap"}
DASHBOARDS_HOME=${DASHBOARDS_HOME:-"/bootstrap/dashboards"}

while ! curl -sf ${GRAFANA_URL}/api/admin/stats >/dev/null 2>&1; do
  echo "Waiting for service to come up ..." && sleep 1
done

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

#######################################################################################
# Global Orgs
#######################################################################################
curl -sf ${GRAFANA_URL}/api/admin/stats | jq
if [ $(curl -sf ${GRAFANA_URL}/api/orgs/1 | jq -r '.name' | grep "Public Portal" | wc -l) -eq 0 ]; then
  curl -sf -XPUT ${GRAFANA_URL}/api/orgs/1 \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Public Portal"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL}/api/orgs/2 | jq -r '.id' | grep 2 | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL}/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi

#######################################################################################
# Global Users
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL}/api/admin/stats | jq -r '.users') -lt 3 ]; then
  curl -sf -XPOST ${GRAFANA_URL}/api/admin/users \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "email":"'"${GRAFANA_USER_PUBLIC}@localhost"'",
          "login":"'"${GRAFANA_USER_PUBLIC}"'",
          "password":"'"${GRAFANA_KEY_PUBLIC}"'",
          "OrgId": 1
        }' | jq
  curl -sf -XPOST ${GRAFANA_URL}/api/admin/users \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "email":"'"${GRAFANA_USER_PRIVATE}@localhost"'",
          "login":"'"${GRAFANA_USER_PRIVATE}"'",
          "password":"'"${GRAFANA_KEY_PRIVATE}"'",
          "OrgId": 2
        }' | jq
  curl -sf -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
  USER_ID=$(curl -sf ${GRAFANA_URL}/api/users/lookup?loginOrEmail=${GRAFANA_USER_PUBLIC} | jq -r '.id')
  curl -sf -XPUT ${GRAFANA_URL}/api/admin/users/${USER_ID}/permissions \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "isGrafanaAdmin": true
        }' | jq
  curl -sf -XPATCH ${GRAFANA_URL}/api/org/users/${USER_ID} \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "role": "Admin"
        }' | jq
  curl -sf ${GRAFANA_URL_PUBLIC}/api/org/users | jq -r '.[0]'
  curl -sf -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
  USER_ID=$(curl -sf ${GRAFANA_URL}/api/users/lookup?loginOrEmail=${GRAFANA_USER_PRIVATE} | jq -r '.id')
  curl -sf -XPUT ${GRAFANA_URL}/api/admin/users/${USER_ID}/permissions \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "isGrafanaAdmin": true
        }' | jq
  curl -sf -XPATCH ${GRAFANA_URL}/api/org/users/${USER_ID} \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "role": "Admin"
        }' | jq
  curl -sf ${GRAFANA_URL_PRIVATE}/api/org/users | jq -r '.[0]'
fi
curl -sf ${GRAFANA_URL}/api/admin/stats | jq

#######################################################################################
# Public Datasources
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/datasources/name/InfluxDB_V2 | jq -r '.name' | grep InfluxDB_V2 | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/datasources \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V2",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_HTTP_PORT}"'",
          "access": "proxy",
          "isDefault": true,
          "jsonData": {
            "version": "Flux",
            "organization": "'"${INFLUXDB_ORG}"'",
            "defaultBucket": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'",
            "timeout": "60"
          },
          "secureJsonData": {
            "token": "'"${INFLUXDB_TOKEN_PUBLIC_V2}"'"
          },
          "secureJsonFields": {
            "token": true
          }
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/datasources/name/InfluxDB_V1 | grep InfluxDB_V1 | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/datasources \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V1",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_HTTP_PORT}"'",
          "access": "proxy",
          "isDefault": false,
          "database": "'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'",
          "user": "'"${INFLUXDB_USER_PUBLIC}"'",
          "secureJsonData": {
            "password": "'"${INFLUXDB_TOKEN_PUBLIC_V1}"'"
          }
        }' | jq
fi
curl -sf ${GRAFANA_URL_PUBLIC}/api/datasources | jq

#######################################################################################
# Public Folders
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/folders | grep Public_Default | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Default",
          "title": "Public_Default"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/folders | grep Public_Mobile | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Mobile",
          "title": "Public_Mobile"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/folders | grep Public_Tablet | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Tablet",
          "title": "Public_Tablet"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/folders | grep Public_Desktop | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PUBLIC}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Public_Desktop",
          "title": "Public_Desktop"
        }' | jq
fi
curl -sf ${GRAFANA_URL_PUBLIC}/api/folders | jq

#######################################################################################
# Public Dashboards
#######################################################################################
export GRAFANA_URL=${GRAFANA_URL_PUBLIC}
find ${DASHBOARDS_HOME}/public -name dashboard_* -exec ${LIBRARIES_HOME}/grizzly/grr -J ${LIBRARIES_HOME}/grafonnet-lib -J ${DASHBOARDS_HOME} apply {} \;

#######################################################################################
# Default Dashboard
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PUBLIC}/api/org/preferences | grep public-home-default | wc -l) -eq 0 ]; then
  curl -sf -XPATCH ${GRAFANA_URL_PUBLIC}/api/org/preferences \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "timezone":"awst",
          "homeDashboardUID":"public-home-default"
        }' | jq
fi

#######################################################################################
# Private Datasources
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/datasources/name/InfluxDB_V2 | jq -r '.name' | grep InfluxDB_V2 | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/datasources \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V2",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_HTTP_PORT}"'",
          "access": "proxy",
          "isDefault": true,
          "jsonData": {
            "version": "Flux",
            "organization": "'"${INFLUXDB_ORG}"'",
            "defaultBucket": "'"${INFLUXDB_BUCKET_DATA_PRIVATE}"'",
            "timeout": "60"
          },
          "secureJsonData": {
            "token": "'"${INFLUXDB_TOKEN}"'"
          },
          "secureJsonFields": {
            "token": true
          }
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/datasources/name/InfluxDB_V1 | grep InfluxDB_V1 | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/datasources \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V1",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB_HOST}:${INFLUXDB_HTTP_PORT}"'",
          "access": "proxy",
          "isDefault": false,
          "database": "'"${INFLUXDB_BUCKET_DATA_PRIVATE}"'",
          "user": "'"${INFLUXDB_USER_PRIVATE}"'",
          "secureJsonData": {
            "password": "'"${INFLUXDB_TOKEN}"'"
          }
        }' | jq
fi
curl -sf ${GRAFANA_URL_PRIVATE}/api/datasources | jq

#######################################################################################
# Private Folders
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/folders | grep Private_Default | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Default",
          "title": "Private_Default"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/folders | grep Private_Mobile | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Mobile",
          "title": "Private_Mobile"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/folders | grep Private_Tablet | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Tablet",
          "title": "Private_Tablet"
        }' | jq
fi
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/folders | grep Private_Desktop | wc -l) -eq 0 ]; then
  curl -sf -XPOST ${GRAFANA_URL_PRIVATE}/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Desktop",
          "title": "Private_Desktop"
        }' | jq
fi
curl -sf ${GRAFANA_URL_PRIVATE}/api/folders | jq

#######################################################################################
# Private Dashboards
#######################################################################################
export GRAFANA_URL=${GRAFANA_URL_PRIVATE}
find ${DASHBOARDS_HOME}/private -name dashboard_* -exec ${LIBRARIES_HOME}/grizzly/grr -J ${LIBRARIES_HOME}/grafonnet-lib -J ${DASHBOARDS_HOME} apply {} \;

#######################################################################################
# Default Dashboard
#######################################################################################
if [ $(curl -sf ${GRAFANA_URL_PRIVATE}/api/org/preferences | grep private-home-default | wc -l) -eq 0 ]; then
  curl -sf -XPATCH ${GRAFANA_URL_PRIVATE}/api/org/preferences \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "timezone":"awst",
          "homeDashboardUID":"private-home-default"
        }' | jq
fi


echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
