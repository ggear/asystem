/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -s "http://localhost:${WRANGLE_HTTP_PORT}/health" | jq -r '.status')" = "healthy" ]
