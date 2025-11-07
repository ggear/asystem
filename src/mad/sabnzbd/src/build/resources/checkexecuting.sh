READY="$(curl "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0")" &&
  [ "$(jq -r '.status.diskspace1 // 0' <<<"${READY}")" -gt 10 ] &&
  [ "$(jq -r '[.status.servers[]?.servertotalconn // 0] | add' <<<"${READY}")" -gt 0 ]
