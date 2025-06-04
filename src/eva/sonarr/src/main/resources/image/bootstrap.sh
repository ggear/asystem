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

# Setup Root Folder
curl -X POST "${SONARR_URL}/api/v3/rootfolder" -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d \
  '{
      "path": "/tmp",
      "accessible": true
    }'

# Setup Indexer
if [ $(curl -sf -X GET "${SONARR_URL}/api/v3/indexer" -H "X-Api-Key: ${SONARR_API_KEY}" | jq 'length == 1 and .[0].name == "NZBgeek"') != "true" ]; then
  curl -X POST "${SONARR_URL}/api/v3/indexer" -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d \
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
    }'
fi

# Setup Download Client
if [ $(curl -sf -X GET "${SONARR_URL}/api/v3/downloadclient" -H "X-Api-Key: ${SONARR_API_KEY}" | jq 'length == 1 and .[0].name == "SABnzbd"') != "true" ]; then
  curl -X POST "${SONARR_URL}/api/v3/downloadclient" -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d \
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
      }'
fi

# --- CONFIGURATION ---
CF_NAME="Prefer H.265"
CF_SCORE=100

## --- STEP 1: Check or Create Custom Format ---
#cf_id=$(curl -s \
#  "${SONARR_URL}/api/v3/customformat" \
#  -H "X-Api-Key: ${SONARR_API_KEY}" |
#  jq -r '.[] | select(.name == "'"${CF_NAME}"'") | .id')
#
#if [[ -n "${cf_id}" ]]; then
#  echo "✅ Custom Format \"${CF_NAME}\" already exists (ID: ${cf_id})"
#else
#  echo "🔧 Creating Custom Format \"${CF_NAME}\"..."
#
#  cf_id=$(curl -s -X POST \
#    "${SONARR_URL}/api/v3/customformat" \
#    -H "X-Api-Key: ${SONARR_API_KEY}" \
#    -H "Content-Type: application/json" \
#    -d \
#    '{
#        "name": '"${CF_NAME}"'",
#        "includeCustomFormatWhenRenaming": false,
#        "specifications": [
#          {
#              "name": "x265/HEVC",
#              "implementation": "ReleaseTitleSpecification",
#              "negate": false,
#              "required": false,
#              "fields": [
#                  { "name": "value", "value": "x265|h265|hevc" }
#              ]
#          }
#        ]
#      }' | jq -r '.id')
#
#  if [[ -n "${cf_id}" && "${cf_id}" != "null" ]]; then
#    echo "✅ Created Custom Format \"${CF_NAME}\" (ID: ${cf_id})"
#  fi
#fi
#
## --- STEP 2: Apply to Quality Profiles ---
#profiles=$(curl -s \
#  "${SONARR_URL}/api/v3/qualityprofile" \
#  -H "X-Api-Key: ${SONARR_API_KEY}")
#
#echo "${profiles}" | jq -c '.[]' | while read -r profile_json; do
#  profile_id=$(echo "${profile_json}" | jq -r '.id')
#  profile_name=$(echo "${profile_json}" | jq -r '.name')
#
#  # Check if CF already exists in profile
#  already_set=$(echo "${profile_json}" | jq -r '.formatItems // [] | map(select(.format.id == '"${cf_id}"')) | length')
#
#  if [[ "${already_set}" -gt 0 ]]; then
#    echo "➖ \"${profile_name}\" already contains \"${CF_NAME}\" — skipping."
#    continue
#  fi
#
#  echo "➕ Adding \"${CF_NAME}\" (ID: ${cf_id}, Score: ${CF_SCORE}) to \"${profile_name}\"..."
#
#  # Add new format item
#  updated_json=$(echo "${profile_json}" | jq '.formatItems = (.formatItems // [] + [{"format": {"id": '"${cf_id}"'}, "score": '"${CF_SCORE}"'}])')
#
#  update_response=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
#    "${SONARR_URL}/api/v3/qualityprofile/${profile_id}" \
#    -d "${updated_json}" \
#    -H "X-Api-Key: ${SONARR_API_KEY}" \
#    -H "Content-Type: application/json")
#
#  if [[ "${update_response}" == "200" ]]; then
#    echo "✅ Updated \"${profile_name}\" successfully."
#  else
#    echo "❌ Failed to update \"${profile_name}\" (HTTP ${update_response})"
#  fi
#done

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

set +eo pipefail

MESSAGE="Waiting for service to become ready ..."
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkready.sh"; do
  echo "${MESSAGE}" && sleep 1
done
echo "----------" && echo "Service has started"