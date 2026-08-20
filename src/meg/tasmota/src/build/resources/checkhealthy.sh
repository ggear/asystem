/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf -m 5 http://localhost:80/ | grep -qE 'href="http://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/"'
