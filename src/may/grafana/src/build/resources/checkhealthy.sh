/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -o /dev/null -s -w "%{http_code}" "https://grafana.local.janeandgraham.com/d/public-home-default/home")" = "200" ]
