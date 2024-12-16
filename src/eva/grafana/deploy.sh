#!/bin/bash

WORKING_DIR=${PWD}

export $(xargs <.env)

[ -d /usr/local/Cellar/go@1.16/1.16.15 ] && export GOROOT=/usr/local/Cellar/go@1.16/1.16.15/libexec
[ -d /opt/homebrew/Cellar/go\@1.16/1.16.15 ] && export GOROOT=/opt/homebrew/Cellar/go\@1.16/1.16.15/libexec

export GOPATH=${HOME}/.go
export PATH=${GOPATH}/bin:${GOROOT}/bin:$PATH

export INFLUXDB_SERVICE=${INFLUXDB_SERVICE_PROD}

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_TOKEN}@${GRAFANA_SERVICE_PROD}:${GRAFANA_HTTP_PORT}
export GRAFANA_URL_PUBLIC=http://${GRAFANA_USER_PUBLIC}:${GRAFANA_TOKEN_PUBLIC}@${GRAFANA_SERVICE_PROD}:${GRAFANA_HTTP_PORT}
export GRAFANA_URL_PRIVATE=http://${GRAFANA_USER_PRIVATE}:${GRAFANA_TOKEN_PRIVATE}@${GRAFANA_SERVICE_PROD}:${GRAFANA_HTTP_PORT}

export LIBRARIES_HOME=${WORKING_DIR}/src/main/resources/libraries
export DASHBOARDS_HOME=${WORKING_DIR}/src/main/resources/image/dashboards

cd ${LIBRARIES_HOME}/grizzly
make dev

${WORKING_DIR}/src/main/resources/image/bootstrap.sh
