#!/bin/bash

. ./../.env

echo -n "Refreshing metadata ... "
for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
  curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
done
echo "done"
