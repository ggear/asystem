READY="$(curl -K - "${GRAFANA_URL}/api/admin/stats" <<<"user = \"${GRAFANA_USER}:${GRAFANA_TOKEN}\"")" &&
  [ "$(jq -er .orgs <<<"${READY}")" -eq 1 ] &&
  [ "$(jq -er .dashboards <<<"${READY}")" -ge "$(find /asystem/mnt/dashboards/generated /asystem/mnt/dashboards/custom -name '*.yaml' | wc -l)" ]
