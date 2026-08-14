/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -fsS "http://localhost:${CLOUDFLARE_METRICS_PORT}/ready" >/dev/null
