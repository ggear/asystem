/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf -m 5 http://localhost:80/ | grep -qE 'href="http://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/"' &&
  [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' http://localhost:80/mqtt)" -lt 500 ]
