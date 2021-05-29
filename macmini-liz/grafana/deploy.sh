#!/bin/sh

. .env
export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}
cd src/main/resources/config/grizzly
make dev
cd ../grafonnet-lib

#curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
#./../grizzly/grr apply ./../dashboards/template/generated/dashboards_all.jsonnet

if [ $(curl --silent ${GRAFANA_URL}/api/orgs/2 | jq -r '.id' | grep 2 | wc -l) -eq 0 ]; then
  curl -XPOST --silent ${GRAFANA_URL}/api/orgs \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "Private Portal"
        }' | jq
fi

curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
./../grizzly/grr apply ./../dashboards/template/private/generated/dashboards_all.jsonnet
