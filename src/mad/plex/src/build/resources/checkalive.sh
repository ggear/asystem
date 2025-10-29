curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/identity" | grep -q "machineIdentifier"
