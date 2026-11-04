curl -sf --max-time 10 -X POST -H 'Content-Type: application/json' -d '{}' "http://${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT}/v2/repository/index" |
  jq -r '.[] | "Serving model [\(.name)] version [\(.version)] state [\(.state)]"'
