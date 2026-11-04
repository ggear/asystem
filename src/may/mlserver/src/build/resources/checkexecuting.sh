/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf --max-time 5 "http://${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT}/v2/health/ready" >/dev/null
