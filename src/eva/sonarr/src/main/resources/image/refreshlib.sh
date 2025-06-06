#!/usr/bin/env bash

auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
series_ids=$(curl -s "${SONARR_URL}/api/v3/series" "${auth_header[@]}" | jq -r '.[].id')
for series_id in $series_ids; do
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
    -d '{"name": "RescanSeries", "seriesId": '"${series_id}"'}')
  if [[ "$status" == "201" ]]; then
    echo "✅ Rescan started for series $series_id"
  else
    echo "❌ Failed to start rescan for series $series_id (HTTP $status)"
  fi
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
    -d '{"name": "DownloadedEpisodesScan", "seriesId": '"${series_id}"'}')
  if [[ "$status" == "201" ]]; then
    echo "✅ Downloaded-Rescan started for series $series_id"
  else
    echo "❌ Failed to start downloaded-rescan for series $series_id (HTTP $status)"
  fi
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
    -d '{"name": "RefreshSeries", "seriesId": '"${series_id}"'}')
  if [[ "$status" == "201" ]]; then
    echo "✅ Refresh started for series $series_id"
  else
    echo "❌ Failed to start refresh for series $series_id (HTTP $status)"
  fi
done
