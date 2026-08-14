/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -fsS "http://localhost:${CLOUDFLARED_METRICS_PORT}/ready" >/dev/null
