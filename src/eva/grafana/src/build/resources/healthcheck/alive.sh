[ "$(curl "${GRAFANA_URL}/api/health" | jq -er .database | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" == "ok" ]
