/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/identity" | xq -e '.MediaContainer."@claimed" == "1"' >/dev/null &&
  curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq -e '.MediaContainer.Directory | length > 0' >/dev/null
