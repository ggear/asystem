#!/bin/bash

WORKING_DIR=${PWD}

export $(xargs <.env)

export GOROOT=/opt/homebrew/Cellar/go\@1.16/1.16.15/libexec
export GOPATH=${HOME}/.go
export PATH=${GOPATH}/bin:${GOROOT}/bin:$PATH

export INFLUXDB_HOST=${INFLUXDB_HOST_PROD}
export INFLUXDB_IP=${INFLUXDB_IP_PROD}

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}
export GRAFANA_URL_PUBLIC=http://${GRAFANA_USER_PUBLIC}:${GRAFANA_KEY_PUBLIC}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}
export GRAFANA_URL_PRIVATE=http://${GRAFANA_USER_PRIVATE}:${GRAFANA_KEY_PRIVATE}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}

export LIBRARIES_HOME=${WORKING_DIR}/src/main/resources/libraries
export DASHBOARDS_HOME=${WORKING_DIR}/src/main/resources/config/dashboards/instance

cd ${LIBRARIES_HOME}/grizzly
make dev

${WORKING_DIR}/src/main/resources/config/bootstrap.sh
