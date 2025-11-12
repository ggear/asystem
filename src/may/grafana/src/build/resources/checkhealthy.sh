/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -o /dev/null -s -w "%{http_code}" "https://data.janeandgraham.com/d/public-home-default/home")" = "200" ]
