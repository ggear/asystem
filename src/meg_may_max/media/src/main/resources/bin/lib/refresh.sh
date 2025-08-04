#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

PLEX_URL="http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}"

# 🔧 Define Plex library names (TYPES) and matching folder scopes
SCOPES=("docos" "kids")
TYPES=("Series" "Movies")

# ⛓ Loop over each Plex library and scope
for i in "${!TYPES[@]}"; do
  TYPE="${TYPES[$i]}"         # e.g. Series
  SCOPE="${SCOPES[$i]}"       # e.g. parents
  TYPE_LC=$(echo "$TYPE" | tr '[:upper:]' '[:lower:]')

  echo "🔍 Processing Plex library: $TYPE (scope: $SCOPE)"

  # 🎯 Get section ID
  SECTION_XML=$(curl -s "${PLEX_URL}/library/sections?X-Plex-Token=${PLEX_TOKEN}")
  SECTION_ID=$(echo "$SECTION_XML" | xmllint --xpath "//Directory[@title='${TYPE}']/@key" - 2>/dev/null | sed -E 's/[^0-9]*//g')

  echo $SECTION_XML
  echo curl -s "${PLEX_URL}/library/sections?X-Plex-Token=${PLEX_TOKEN}"

  if [ -n "$SECTION_ID" ]; then
    echo "📚 Found section ID: $SECTION_ID"

    # 📂 Get current paths
    EXISTING_PATHS=$(curl -s "${PLEX_URL}/library/sections/${SECTION_ID}?X-Plex-Token=${PLEX_TOKEN}" |
      xmllint --xpath "//Location/@path" - 2>/dev/null |
      sed -E 's/path="/\n/g' | sed '/^$/d;s/"//g')
    EXISTING_GREP=$(printf "%s\n" ${EXISTING_PATHS})

    # 🔍 Discover matching directories (e.g. /share/.../parents/series)
    find ${SHARE_ROOT} -maxdepth 4 -path "*/${SCOPE}/${TYPE_LC}" | sort | while read -r dir; do
      if ! echo "$EXISTING_GREP" | grep -Fxq "$dir"; then
        echo "➕ Adding NEW path: $dir"
#        RESP=$(curl -s -w "%{http_code}" -o /tmp/plex_add_out \
#          -X PUT "${PLEX_URL}/library/sections/${SECTION_ID}/locations" \
#          -H "X-Plex-Token: ${PLEX_TOKEN}" \
#          --data-urlencode "path=${dir}")
#        if [ "$RESP" != "200" ]; then
#          echo "❌ Failed to add: $dir (HTTP $RESP)"
#          cat /tmp/plex_add_out
#        fi
      else
        echo "✅ Already exists, skipping: $dir"
      fi
    done

    # ✅ Always trigger scan
    echo "🔄 Triggering scan on section $SECTION_ID (always)"
    curl -s -w "%{http_code}" -o /tmp/plex_scan_out \
      "${PLEX_URL}/library/sections/${SECTION_ID}/refresh?X-Plex-Token=${PLEX_TOKEN}" |
      grep -q '^200$' || {
      echo "❌ Scan failed for section $SECTION_ID"
      cat /tmp/plex_scan_out
    }

  else
    echo "❌ Could not find Plex library: $TYPE"
  fi
done

#echo -n "Refreshing 'http://${PLEX_SERVICE_PROD}/libraries' ... "
#for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
#  curl -sf http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
#done
#echo "done"

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
