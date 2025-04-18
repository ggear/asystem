READY="$(curl "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0")" &&
  [ "$(jq -er '.status.paused' <<<"${READY}")" == "false" ] &&
  [ "$(jq -er '[.status.servers[].servertotalconn] | add' <<<"${READY}")" -gt 0 ]
