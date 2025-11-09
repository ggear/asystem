/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -s "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0" | jq -e '.status.diskspace1 // 0 > 10 and ([.status.servers[]?.servertotalconn // 0] | add) > 0'
