#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

SERVICE_WAIT_ALIVE_SECONDS=900
SERVICE_WAIT_EXECUTING_SECONDS=900

wait_service() {
  local script="$1" label="$2" interval="$3" timeout="$4" waited=0
  ((interval > 0)) || interval=1
  while ! "${ASYSTEM_HOME}/${script}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      echo "Waiting for service to ${label} ... failed after [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 5
      echo "ERROR: Service failed to ${label} within [${timeout}] seconds" >&2
      exit 1
    fi
    if ((waited % 30 == 0)); then
      echo "Waiting for service to ${label} ... waited [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 3
    fi
    sleep "${interval}"
    waited=$((waited + interval))
  done
  echo "Waiting for service to ${label} ... done after [${waited}] of [${timeout}] seconds"
}

wait_service "checkalive.sh" "come alive" 1 "${SERVICE_WAIT_ALIVE_SECONDS}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

#######################################################################################
# Current Stats
#######################################################################################
curl -sf "${GRAFANA_URL}"/api/admin/stats | jq

#######################################################################################
# Grizzly config
#######################################################################################
grr config create-context default
grr config set grafana.url ${GRAFANA_URL}
grr config set grafana.user ${GRAFANA_USER}
grr config set grafana.token ${GRAFANA_TOKEN}
grr config create-context private
grr config set grafana.url ${GRAFANA_URL_PRIVATE}
grr config set grafana.user ${GRAFANA_USER_PRIVATE}
grr config set grafana.token ${GRAFANA_TOKEN_PRIVATE}
grr config use-context default
echo "" && echo "$(grr config path):" && echo "" && cat $(grr config path) && grr config check

#######################################################################################
# Global Orgs
#######################################################################################
if [ "$(curl -sf "${GRAFANA_URL}"/api/orgs/2 | jq -r '.id' | grep -c "2")" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL}"/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi

#######################################################################################
# Global Users
#######################################################################################
if [ "$(curl -sf "${GRAFANA_URL}"/api/admin/stats | jq -r '.users')" -lt 2 ]; then
  curl -sf -XPOST "${GRAFANA_URL}"/api/admin/users \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "email":"'"${GRAFANA_USER_PRIVATE}@localhost"'",
          "login":"'"${GRAFANA_USER_PRIVATE}"'",
          "password":"'"${GRAFANA_TOKEN_PRIVATE}"'",
          "OrgId": 2
        }' | jq
  curl -sf -XPOST --silent "${GRAFANA_URL}"/api/user/using/2 | jq
  USER_ID="$(curl -sf "${GRAFANA_URL}"/api/users/lookup?loginOrEmail="${GRAFANA_USER_PRIVATE}" | jq -r '.id')"
  curl -sf -XPUT "${GRAFANA_URL}"/api/admin/users/"${USER_ID}"/permissions \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "isGrafanaAdmin": true
        }' | jq
  curl -sf -XPATCH "${GRAFANA_URL}"/api/org/users/"${USER_ID}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "role": "Admin"
        }' | jq
  curl -sf "${GRAFANA_URL_PRIVATE}"/api/org/users | jq -r '.[0]'
fi
curl -sf "${GRAFANA_URL}"/api/admin/stats | jq

#######################################################################################
# Private Datasource
#######################################################################################
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/datasources/name/InfluxDB_V3 | jq -r '.name' | grep InfluxDB_V3 | wc -l)" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL_PRIVATE}"/api/datasources \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "InfluxDB_V3",
          "type": "influxdb",
          "url": "http://'"${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}"'",
          "access": "proxy",
          "isDefault": true,
          "jsonData": {
            "version": "SQL",
            "dbName": "'"${INFLUXDB3_DATABASE_HOME}"'",
            "timeout": 60,
            "httpMode": "POST",
            "insecureGrpc": true,
            "metadata": [
              {
                "database": "'"${INFLUXDB3_DATABASE_HOME}"'"
              }
            ]
          },
          "secureJsonData": {
            "token": "'"${INFLUXDB3_TOKEN_HOME}"'"
          },
          "secureJsonFields": {
            "token": true
          }
        }' | jq
fi
curl -sf "${GRAFANA_URL_PRIVATE}"/api/datasources | jq

#######################################################################################
# Private Folders
#######################################################################################
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/folders | grep Private_Default | wc -l)" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL_PRIVATE}"/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Default",
          "title": "Private_Default"
        }' | jq
fi
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/folders | grep Private_Mobile | wc -l)" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL_PRIVATE}"/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Mobile",
          "title": "Private_Mobile"
        }' | jq
fi
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/folders | grep Private_Tablet | wc -l)" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL_PRIVATE}"/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Tablet",
          "title": "Private_Tablet"
        }' | jq
fi
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/folders | grep Private_Desktop | wc -l)" -eq 0 ]; then
  curl -sf -XPOST "${GRAFANA_URL_PRIVATE}"/api/folders \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "uid": "Private_Desktop",
          "title": "Private_Desktop"
        }' | jq
fi
curl -sf "${GRAFANA_URL_PRIVATE}"/api/folders | jq

#######################################################################################
# Private Dashboards
#######################################################################################
export GRAFANA_URL=$GRAFANA_URL_PRIVATE
export GRAFANA_USER=$GRAFANA_USER_PRIVATE
export GRAFANA_TOKEN=$GRAFANA_TOKEN_PRIVATE
find "${ASYSTEM_HOME}"/dashboards/private -name "dashboard_*" -exec grr -J "${ASYSTEM_HOME}"/libraries/grafonnet-lib -J "${ASYSTEM_HOME}"/dashboards apply {} \;

#######################################################################################
# Default Dashboard
#######################################################################################
if [ "$(curl -sf "${GRAFANA_URL_PRIVATE}"/api/org/preferences | grep private-home-default | wc -l)" -eq 0 ]; then
  curl -sf -XPATCH "${GRAFANA_URL_PRIVATE}"/api/org/preferences \
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

wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_EXECUTING_SECONDS}"
echo "----------" && echo "✅ Service has started"