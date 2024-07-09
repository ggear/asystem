#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/../../../.env

IFS=$'\n'
for VERSIONS in $(find "/share" -type f -path '*/Plex Versions/*/*.mp4' ! -path '.inProgress'); do
  echo "${VERSIONS}"
done

#echo -n "Refreshing libraries ... "
#for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
#  curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
#done
#echo "done"

# Detect completed 'Plex Versions', ignore in progress
# Move Season/Movie out of tree
# Refresh Library
# Move Season/Moive backinto tree, replacing original, moving original to baclup to be removed by clean
# Rename files, adding prefix, removing srt suffix
# remove empty 'Plex Versions' dirs
# Refresh Library

# TODO: Check versions not queued up to be recreated, they seem to be with the process, maybe dont do at all and just re-encode out of plex band?
