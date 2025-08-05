#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

PLEX_URL="http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}"

declare -A SCOPES_MAP
declare -A TYPES_MAP
SCOPE_TYPE_DIRS=$(find ${SHARE_ROOT}/*/media -mindepth 2 -maxdepth 2 -type d ! -path */audio | tr ' ' '\n')
for path in $SCOPE_TYPE_DIRS; do
  SCOPES_MAP["$(echo "$path" | awk -F'/' '{print $(NF-1)}')"]=1
  TYPES_MAP["$(echo "$path" | awk -F'/' '{print $NF}')"]=1
done
SCOPES=($(printf "%s\n" "${!SCOPES_MAP[@]}" | sort))
TYPES=($(printf "%s\n" "${!TYPES_MAP[@]}" | sort))
for i in "${!SCOPES[@]}"; do
  lower="${SCOPES[i],,}"
  SCOPES[i]="${lower^}"
done
for i in "${!TYPES[@]}"; do
  lower="${TYPES[i],,}"
  TYPES[i]="${lower^}"
done

for i in "${!TYPES[@]}"; do
  for j in "${!SCOPES[@]}"; do
    TYPE="${TYPES[$i]}"
    SCOPE="${SCOPES[$j]}"
    echo $SCOPE $TYPE
  done
done

LIBRARIES_XML=$(curl -s "${PLEX_URL}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xmllint --format -)
echo "$LIBRARIES_XML" | xmllint --format - |
  sed -n '/<Directory /,/<\/Directory>/p' |
  awk '
    /<Directory / {
      # Extract title attribute from Directory start tag
      match($0, /title="[^"]+"/)
      title = substr($0, RSTART+7, RLENGTH-8)
      next
    }
    /<Location / {
      # Extract path attribute
      match($0, /path="[^"]+"/)
      path = substr($0, RSTART+6, RLENGTH-7)
      print title "|" path
    }
  ' | while IFS="|" read -r title path; do

  #  echo "$title: $path"
  if [[ -n "${TYPES_MAP[$title]}" ]]; then
    echo "'$title' exists in TYPES_MAP"
  else
    echo "'$title' does NOT exist in TYPES_MAP"
  fi

done

exit 1

#echo -n "Refreshing 'http://${PLEX_SERVICE_PROD}/libraries' ... "
#for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
#  curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
#done

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
