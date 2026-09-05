/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl "http://localhost:${CLOUDFLARE_METRICS_PORT}/ready" | jq -er '.readyConnections')" -ge 1 ]
