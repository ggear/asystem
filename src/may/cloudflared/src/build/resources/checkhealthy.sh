/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -fsS "http://localhost:${CLOUDFLARED_METRICS_PORT}/ready" | jq -e '.readyConnections >= 1' >/dev/null
