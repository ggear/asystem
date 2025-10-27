[ $(ps aux | grep weewxd | grep python | grep -v grep | wc -l) -eq 1 ] &&
  [ "$(curl -sf -o /dev/null -w "%{http_code}" http://${WEEWX_SERVICE}:${WEEWX_HTTP_PORT})" = "200" ]
