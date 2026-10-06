/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  DATASOURCES="$(curl -K - "${GRAFANA_URL}/api/datasources" <<<"user = \"${GRAFANA_USER}:${GRAFANA_TOKEN}\"" | jq -er '.[].uid')" &&
  HEALTHY="$(for DATASOURCE in ${DATASOURCES}; do curl -K - "${GRAFANA_URL}/api/datasources/uid/${DATASOURCE}/health" <<<"user = \"${GRAFANA_USER}:${GRAFANA_TOKEN}\"" | jq -r .status; done)" &&
  [ "$(grep -cx OK <<<"${HEALTHY}")" -eq "$(wc -w <<<"${DATASOURCES}")" ] &&
  curl "${GRAFANA_DOMAIN_URL}/api/search?limit=1" | jq -e 'length > 0' >/dev/null
