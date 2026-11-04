/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf --max-time 10 -X POST -H 'Content-Type: application/json' -d '{}' "http://${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT}/v2/repository/index" | jq -e 'all(.[]; .state == "READY")' >/dev/null
