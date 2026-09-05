/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -L -o /dev/null -s -w "%{http_code}" "https://grafana.proxy.janeandgraham.com")" = "200" ]
