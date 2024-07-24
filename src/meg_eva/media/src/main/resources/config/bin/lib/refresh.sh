#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/../.env_media"

echo -n "Refreshing 'http://${PLEX_SERVICE_PROD}/libraries' ... "
for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
  curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
done
echo "done"
