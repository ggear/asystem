#!/bin/bash

. ./../.env

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <share-dir>"
  exit 1
fi



#echo -n "Refreshing metadata for ${SHARE_DIR} ... "

echo http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}

echo http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections/29/refresh?X-Plex-Token=${PLEX_TOKEN}

#echo "done"
