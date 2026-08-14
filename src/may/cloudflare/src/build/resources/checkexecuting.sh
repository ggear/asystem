/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -o /dev/null -w "%{http_code}" "http://localhost:${CLOUDFLARE_METRICS_PORT}/ready")" = "200" ]
