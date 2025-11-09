/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq -e '.MediaContainer.Location | length > 0' >/dev/null &&
  [ "$(curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq -r '.MediaContainer.Location[]."@path"' | wc -l)" -eq "$(find /share -mindepth 4 -maxdepth 4 -path '*/media/*' ! -path '*audio*' -type d | wc -l)" ]
