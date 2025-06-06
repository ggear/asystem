#!/usr/bin/env bash

#payload=$(jq -n \
#  --arg name "ImportSeries" \
#  --arg path "${MEDIA_SERIES_DIR}" \
#  '{ name: $name, path: $path }')
#
#status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${SONARR_URL}/api/v3/command" \
#  -H "X-Api-Key: ${SONARR_API_KEY}" \
#  -H "Content-Type: application/json" \
#  -d "${payload}")
#
#if [[ "${status}" -eq 201 ]]; then
#  echo "✅ Import from '${MEDIA_SERIES_DIR}' triggered"
#else
#  echo "❌ Failed to trigger import from '${MEDIA_SERIES_DIR}', HTTP ${status}" >&2
#fi

#series=$(curl -s "${SONARR_URL}/api/v3/series" -H "X-Api-Key: ${SONARR_API_KEY}")
#echo "${series}" | jq -c '.[]' | while read -r item; do
#  id=$(echo "${item}" | jq -r '.id')
#  title=$(echo "${item}" | jq -r '.title')
#  payload=$(jq -n --argjson seriesId "${id}" '{ name: "RescanSeries", seriesId: $seriesId }')
#  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${SONARR_URL}/api/v3/command" \
#    -H "X-Api-Key: ${SONARR_API_KEY}" \
#    -H "Content-Type: application/json" \
#    -d "${payload}")
#  if [[ "${status}" -eq 201 ]]; then
#    echo "✅ ${title} (ID: ${id}) rescan triggered"
#  else
#    echo "❌ ${title} (ID: ${id}) failed to trigger rescan, HTTP ${status}" >&2
#  fi
#done
