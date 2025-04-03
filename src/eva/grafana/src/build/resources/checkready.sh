READY="$(curl "${GRAFANA_URL}/api/admin/stats")" &&
  [ "$(jq -er .orgs <<<"${READY}")" -eq 2 ] &&
  [ "$(jq -er .dashboards <<<"${READY}")" -ge "$(($(find /asystem/etc/dashboards \( -path "*/public/*" -o -path "*/private/*" \) -name "graph_*\.jsonnet" | wc -l) + 8))" ]
