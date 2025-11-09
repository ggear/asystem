/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(find /share -mindepth 1 -maxdepth 1 | wc -l)" -eq "$(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l)" ] &&
  [ "$(curl -s "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq -x '//Location/@path' | wc -l)" -eq "$(find /share -mindepth 4 -maxdepth 4 -path '*/media/*' ! -path '*audio*' -type d | wc -l)" ]
