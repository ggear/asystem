/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -fsS "https://${NGINX_SERVICE}:${NGINX_HTTP_PORT}/health" | grep -qx "OK"
