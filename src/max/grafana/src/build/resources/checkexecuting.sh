READY="$(curl "${GRAFANA_URL}/api/admin/stats")" &&
  [ "$(jq -er .orgs <<<"${READY}")" -eq 1 ] &&
  [ "$(jq -er .dashboards <<<"${READY}")" -ge "$(find /asystem/mnt/dashboards/generated /asystem/mnt/dashboards/custom -name '*.yaml' | wc -l)" ]
