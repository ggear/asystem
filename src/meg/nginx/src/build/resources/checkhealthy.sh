/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -fsS -o /dev/null -w "%{http_code}" https://home.janeandgraham.com | grep -qx "200"
