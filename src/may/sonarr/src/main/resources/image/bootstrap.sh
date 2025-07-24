#!/usr/bin/env bash

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

MESSAGE="Waiting for service to come alive ..."
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkalive.sh"; do
 echo "${MESSAGE}" && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

###############################################################################
# Configure indexer
###############################################################################
indexers_json=$(curl -s "${SONARR_URL}/api/v3/indexer" -H "X-Api-Key: ${SONARR_API_KEY}")
exists=$(echo "${indexers_json}" | jq -e '.[] | select(.name=="NZBgeek")' >/dev/null 2>&1 && echo "yes" || echo "no")
if [[ "${exists}" == "yes" ]]; then
  echo "✅ Indexer NZBgeek already exists"
else
  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${SONARR_URL}/api/v3/indexer" \
    -d \
    '{
        "name": "NZBgeek",
        "enableRss": true,
        "enableAutomaticSearch": true,
        "enableInteractiveSearch": true,
        "supportsRss": true,
        "supportsSearch": true,
        "protocol": "usenet",
        "priority": 25,
        "implementation": "Newznab",
        "configContract": "NewznabSettings",
        "tags": [],
        "fields": [
            { "name": "baseUrl", "value": "https://api.nzbgeek.info" },
            { "name": "apiKey", "value": "'"${GEEK_KEY}"'" }
        ]
    }' \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json")
  if [[ "${response}" == 2* ]]; then
    echo "✅ Added indexer NZBgeek"
  else
    echo "❌ Failed to add indexer NZBgeek (HTTP ${response})"
  fi
fi
###############################################################################

###############################################################################
# Configure download client
###############################################################################
download_clients_json=$(curl -s "${SONARR_URL}/api/v3/downloadclient" -H "X-Api-Key: ${SONARR_API_KEY}")
sab_exists=$(echo "${download_clients_json}" | jq -e '.[] | select(.name=="SABnzbd")' >/dev/null 2>&1 && echo "yes" || echo "no")
if [[ "${sab_exists}" == "yes" ]]; then
  echo "✅ Download client SABnzbd already exists"
else
  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${SONARR_URL}/api/v3/downloadclient" \
    -d \
    '{
        "name": "SABnzbd",
        "enable": true,
        "protocol": "usenet",
        "priority": 1,
        "removeCompletedDownloads": false,
        "removeFailedDownloads": false,
        "fields": [
            { "name": "host", "value": "'"${SABNZBD_SERVICE_PROD}"'" },
            { "name": "port", "value": "'"${SABNZBD_HTTP_PORT}"'" },
            { "name": "apiKey", "value": "'"${SABNZBD_API_KEY}"'" },
            { "name": "username", "value": "" },
            { "name": "password", "value": "" },
            { "name": "category", "value": "tv" },
            { "name": "recentTvPriority", "value": -100 },
            { "name": "olderTvPriority", "value": -100 },
            { "name": "seasonFolder", "value": true },
            { "name": "addPaused", "value": false }
        ],
        "implementation": "Sabnzbd",
        "configContract": "SabnzbdSettings",
        "tags": []
     }' \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json")

  if [[ "${response}" == 2* ]]; then
    echo "✅ Added download client SABnzbd"
  else
    echo "❌ Failed to add download client SABnzbd (HTTP ${response})"
  fi
fi
###############################################################################

###############################################################################
# Configure H265 preferred custom format
###############################################################################
CF_SCORE=100
CF_NAMEFILE_SIZE_MIN_GB=1
CF_NAME="HEVC + Size >= ${CF_NAMEFILE_SIZE_MIN_GB} GB"
auth_header=(-H "X-Api-Key: $SONARR_API_KEY")
cf_id=$(curl -s "$SONARR_URL/api/v3/customformat" "${auth_header[@]}" | jq -r '.[] | select(.name=="'"$CF_NAME"'") | .id')
if [[ -n "$cf_id" ]]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$SONARR_URL/api/v3/customformat/$cf_id" "${auth_header[@]}")
  if [[ "$status" == 2* ]]; then
    echo "✅ Deleted existing custom format"
  else
    echo "❌ Failed to delete custom format (HTTP $status)"
  fi
fi
response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$SONARR_URL/api/v3/customformat" \
  "${auth_header[@]}" -H "Content-Type: application/json" \
  -d '{
        "name": "'"$CF_NAME"'",
        "includeCustomFormatWhenRenaming": true,
        "specifications": [
          {
            "name": "265 in Title",
            "implementation": "ReleaseTitleSpecification",
            "negate": false,
            "required": true,
            "fields": [
              { "name": "value", "value": "265" }
            ]
          },
          {
            "name": "Size >= '"$CF_NAMEFILE_SIZE_MIN_GB"' GB",
            "implementation": "SizeSpecification",
            "negate": false,
            "required": true,
            "fields": [
              { "name": "min", "value": "'"$CF_NAMEFILE_SIZE_MIN_GB"'" },
              { "name": "max", "value": "10" }
            ]
          }
        ]
      }')
if [[ "$response" != 2* ]]; then
  echo "❌ Failed to create custom format (HTTP $response)"
else
  cf_id=$(curl -s "$SONARR_URL/api/v3/customformat" "${auth_header[@]}" | jq -r '.[] | select(.name=="'"$CF_NAME"'") | .id')
  echo "✅ Created new custom format with ID $cf_id"
  profiles=$(curl -s "$SONARR_URL/api/v3/qualityProfile" "${auth_header[@]}")
  for row in $(echo "$profiles" | jq -r '.[] | @base64'); do
    _jq() { echo "$row" | base64 --decode | jq -r "$1"; }
    profile_id=$(_jq '.id')
    profile_name=$(_jq '.name')
    full_profile=$(curl -s "$SONARR_URL/api/v3/qualityProfile/$profile_id" "${auth_header[@]}")
    updated_profile=$(echo "$full_profile" | jq '.formatItems[0].score = 100')
    status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$SONARR_URL/api/v3/qualityProfile/$profile_id" \
      "${auth_header[@]}" -H "Content-Type: application/json" -d "$updated_profile")
    if [ "$status" != 2* ]; then
      curl -s -X PUT "$SONARR_URL/api/v3/qualityProfile/$profile_id" \
        "${auth_header[@]}" -H "Content-Type: application/json" -d "$updated_profile"
      echo "❌ Failed to update $profile_name (HTTP $status)"
    fi
    echo "✅ Applied to: $profile_name"
  done
fi
###############################################################################

###############################################################################
# Configure library root folder
###############################################################################
MEDIA_SERIES_DIR="/library"
rootfolders=$(curl -s "${SONARR_URL}/api/v3/rootfolder" -H "X-Api-Key: ${SONARR_API_KEY}")
echo "${rootfolders}" | jq -c '.[]' | while read -r folder; do
  id=$(echo "${folder}" | jq -r '.id')
  status=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${SONARR_URL}/api/v3/rootfolder/${id}" \
    -H "X-Api-Key: ${SONARR_API_KEY}")
  if [ "${status}" == 2* ]; then
    echo "✅ Deleted root folder ID ${id}"
  else
    echo "❌ Failed to delete root folder ID ${id}, HTTP ${status}" >&2
  fi
done
payload=$(jq -n --arg path "${MEDIA_SERIES_DIR}" '{ path: $path, accessible: true }')
status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${SONARR_URL}/api/v3/rootfolder" \
  -H "X-Api-Key: ${SONARR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${payload}")
if [ "${status}" == 2* ]; then
  echo "✅ Successfully added root folder '${MEDIA_SERIES_DIR}'"
else
  echo "❌ Failed to add root folder '${MEDIA_SERIES_DIR}', HTTP ${status}" >&2
fi
###############################################################################

###############################################################################
# Configure grab delay
###############################################################################
GRAB_DELAY_MIN=30
auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
profile=$(curl -s "${SONARR_URL}/api/v3/delayprofile" "${auth_header[@]}" | jq '.[0]')
profile_id=$(echo "$profile" | jq -r '.id')
updated_profile=$(echo "$profile" | jq '.usenetDelay = '"${GRAB_DELAY_MIN}"'')
status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PUT "${SONARR_URL}/api/v3/delayprofile/${profile_id}" \
  "${auth_header[@]}" -H "Content-Type: application/json" \
  -d "$updated_profile")
if [[ "$status" == 2* ]]; then
  echo "✅ Usenet delay updated to ${GRAB_DELAY_MIN} min"
else
  echo "❌ Failed to update usenet delay (HTTP $status)"
fi
###############################################################################

###############################################################################
# Refresh library
###############################################################################
auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
payload='{"name": "DownloadedEpisodesScan"}'
status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${SONARR_URL}/api/v3/command" \
  -H "X-Api-Key: ${SONARR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${payload}")
if [[ "$status" == 2* ]]; then
  echo "✅ Downloaded files scan triggered successfully"
else
  echo "failed"
  curl -s \
    -X POST "${SONARR_URL}/api/v3/command" \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${payload}" | fold -s -w 250 | pr -to 4
  echo "" && echo "❌ Failed to trigger downloaded files scan (HTTP $status)"
fi
series_ids=$(curl -s "${SONARR_URL}/api/v3/series" "${auth_header[@]}" | jq -r '.[].id')
for series_id in $series_ids; do
  payload='{"name": "RescanSeries", "seriesId": '"${series_id}"'}'
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
    -d "${payload}")
  if [[ "$status" == 2* ]]; then
    echo "✅ Rescan started for series $series_id"
  else
    curl -s \
      -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
      -d "${payload}" | fold -s -w 250 | pr -to 4
    echo "" && echo "❌ Failed to start rescan for series $series_id (HTTP $status)"
  fi
  payload='{"name": "RefreshSeries", "seriesId": '"${series_id}"'}'
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
    -d "${payload}")
  if [[ "$status" == 2* ]]; then
    echo "✅ Refresh started for series $series_id"
  else
    curl -s \
      -X POST "${SONARR_URL}/api/v3/command" "${auth_header[@]}" -H "Content-Type: application/json" \
      -d "${payload}" | fold -s -w 250 | pr -to 4
    echo "" && echo "❌ Failed to start refresh for series $series_id (HTTP $status)"
  fi
done
###############################################################################

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

set +eo pipefail

MESSAGE="Waiting for service to become ready ..."
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkready.sh"; do
  echo "${MESSAGE}" && sleep 1
done
echo "----------" && echo "✅ Service has started"