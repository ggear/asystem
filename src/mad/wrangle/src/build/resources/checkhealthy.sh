/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl "http://localhost:${WRANGLE_HTTP_PORT}/health" | grep -q "healthy"
