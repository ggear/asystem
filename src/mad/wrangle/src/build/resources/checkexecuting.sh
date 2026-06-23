/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${WRANGLE_HTTP_PORT}/health")" = "200" ]
