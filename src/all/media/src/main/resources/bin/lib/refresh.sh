#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

echo -n "Refreshing 'http://${PLEX_SERVICE_PROD}/libraries' ... "
RESULT=0
PLEX_SECTIONS=$(curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN})
if [ $? -ne 0 ]; then
  RESULT=1
else
  for PLEX_LIBRARY_KEY in $(echo "${PLEX_SECTIONS}" | xq -x '/MediaContainer/Directory/@key'); do
    curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN} || RESULT=1
  done
fi
if [ ${RESULT} -ne 0 ]; then
  echo "failed"
  exit 1
fi
echo "done"
exit 0

# TODO: Only enable if sonarr automatic download does not break
#  echo -n "Refreshing 'http://${SONARR_SERVICE_PROD}/libraries' ... "
#  auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
#  payload='{"name": "DownloadedEpisodesScan"}'
#  status=$(curl -s -o /dev/null -w "%{http_code}" \
#    -X POST "${SONARR_URL}/api/v3/command" \
#    -H "X-Api-Key: ${SONARR_API_KEY}" \
#    -H "Content-Type: application/json" \
#    -d "${payload}")
#  if [[ "$status" != 2* ]]; then
#    echo "failed"
#    curl -s \
#      -X POST "${SONARR_URL}/api/v3/command" \
#      -H "X-Api-Key: ${SONARR_API_KEY}" \
#      -H "Content-Type: application/json" \
#      -d "${payload}" | fold -s -w 250 | pr -to 4
#    echo "" && exit 1
#  fi
#  series_ids=$(curl -s "${SONARR_URL}/api/v3/series" "${auth_header[@]}" | jq -r '.[].id')
#  for series_id in $series_ids; do
#    payload='{"name": "RescanSeries", "seriesId": '"${series_id}"'}'
#    status=$(curl -s -o /dev/null -w "%{http_code}" \
#      -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
#      -d "${payload}")
#    if [[ "$status" != 2* ]]; then
#      echo "failed"
#      curl -s \
#        -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
#        -d "${payload}" | fold -s -w 250 | pr -to 4
#      echo "" && exit 1
#    fi
#    payload='{"name": "RefreshSeries", "seriesId": '"${series_id}"'}'
#    status=$(curl -s -o /dev/null -w "%{http_code}" \
#      -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
#      -d "${payload}")
#    if [[ "$status" != 2* ]]; then
#      echo "failed"
#      curl -s \
#        -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
#        -d "${payload}" | fold -s -w 250 | pr -to 4
#      echo "" && exit 1
#    fi
#  done
#  echo "done"
