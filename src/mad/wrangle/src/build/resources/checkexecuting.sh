/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl "http://localhost:${WRANGLE_HTTP_PORT}/online" | grep -q "online"
