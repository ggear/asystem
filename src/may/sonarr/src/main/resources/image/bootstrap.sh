#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

MESSAGE="Waiting for service to come alive ... "
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkalive.sh"; do
 echo "${MESSAGE}" && sleep 1
done

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
CF_PROJECTION='{ name, includeCustomFormatWhenRenaming, specifications: [ .specifications[] | { name, implementation, negate, required, fields: [ .fields[] | { name: .name, value: (.value | tostring) } ] } ] }'
auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
cf_declared=$(jq -n --arg name "${CF_NAME}" --arg min "${CF_NAMEFILE_SIZE_MIN_GB}" '{
  name: $name,
  includeCustomFormatWhenRenaming: true,
  specifications: [
    {
      name: "265 in Title",
      implementation: "ReleaseTitleSpecification",
      negate: false,
      required: true,
      fields: [ { name: "value", value: "265" } ]
    },
    {
      name: ("Size >= " + $min + " GB"),
      implementation: "SizeSpecification",
      negate: false,
      required: true,
      fields: [ { name: "min", value: $min }, { name: "max", value: "10" } ]
    }
  ]
}')
cf_existing=$(curl -s "${SONARR_URL}/api/v3/customformat" "${auth_header[@]}" | jq -c '[ .[] | select(.name=="'"${CF_NAME}"'") ]')
cf_count=$(echo "${cf_existing}" | jq 'length')
cf_id=""
if [[ "${cf_count}" -gt 1 ]]; then
  echo "❌ Found [${cf_count}] custom formats named '${CF_NAME}', remove the duplicates by hand" >&2
elif [[ "${cf_count}" -eq 0 ]]; then
  response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "${SONARR_URL}/api/v3/customformat" \
    "${auth_header[@]}" -H "Content-Type: application/json" -d "${cf_declared}")
  if [[ "${response}" != 2* ]]; then
    echo "❌ Failed to create custom format (HTTP ${response})"
  else
    cf_id=$(curl -s "${SONARR_URL}/api/v3/customformat" "${auth_header[@]}" | jq -r '.[] | select(.name=="'"${CF_NAME}"'") | .id')
    echo "✅ Created custom format with ID ${cf_id}"
  fi
else
  cf_id=$(echo "${cf_existing}" | jq -r '.[0].id')
  if [[ "$(echo "${cf_existing}" | jq -cS ".[0] | ${CF_PROJECTION}")" == "$(echo "${cf_declared}" | jq -cS "${CF_PROJECTION}")" ]]; then
    echo "✅ Custom format already configured with ID ${cf_id}"
  else
    cf_updated=$(echo "${cf_declared}" | jq --argjson id "${cf_id}" '. + { id: $id }')
    status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${SONARR_URL}/api/v3/customformat/${cf_id}" \
      "${auth_header[@]}" -H "Content-Type: application/json" -d "${cf_updated}")
    if [[ "${status}" == 2* ]]; then
      echo "✅ Updated drifted custom format with ID ${cf_id}"
    else
      echo "❌ Failed to update custom format with ID ${cf_id} (HTTP ${status})"
    fi
  fi
fi
if [[ -n "${cf_id}" ]]; then
  for profile_id in $(curl -s "${SONARR_URL}/api/v3/qualityProfile" "${auth_header[@]}" | jq -r '.[].id'); do
    profile=$(curl -s "${SONARR_URL}/api/v3/qualityProfile/${profile_id}" "${auth_header[@]}")
    profile_name=$(echo "${profile}" | jq -r '.name')
    profile_score=$(echo "${profile}" | jq -r '.formatItems[] | select(.format=='"${cf_id}"') | .score')
    if [[ -z "${profile_score}" ]]; then
      echo "❌ Custom format ID ${cf_id} absent from quality profile ${profile_name}" >&2
      continue
    fi
    if [[ "${profile_score}" == "${CF_SCORE}" ]]; then
      echo "✅ Score already applied to ${profile_name}"
      continue
    fi
    updated_profile=$(echo "${profile}" | jq '(.formatItems[] | select(.format=='"${cf_id}"') | .score) = '"${CF_SCORE}"'')
    status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${SONARR_URL}/api/v3/qualityProfile/${profile_id}" \
      "${auth_header[@]}" -H "Content-Type: application/json" -d "${updated_profile}")
    if [[ "${status}" == 2* ]]; then
      echo "✅ Applied score to ${profile_name}"
    else
      echo "❌ Failed to update ${profile_name} (HTTP ${status})"
    fi
  done
fi
###############################################################################

###############################################################################
# Configure library root folder
###############################################################################
MEDIA_SERIES_DIR="/library"
rootfolders=$(curl -s "${SONARR_URL}/api/v3/rootfolder" -H "X-Api-Key: ${SONARR_API_KEY}")
if echo "${rootfolders}" | jq -e '.[] | select(.path=="'"${MEDIA_SERIES_DIR}"'")' >/dev/null 2>&1; then
  echo "✅ Root folder '${MEDIA_SERIES_DIR}' already exists"
else
  payload=$(jq -n --arg path "${MEDIA_SERIES_DIR}" '{ path: $path, accessible: true }')
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${SONARR_URL}/api/v3/rootfolder" \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${payload}")
  if [[ "${status}" == 2* ]]; then
    echo "✅ Added root folder '${MEDIA_SERIES_DIR}'"
  else
    echo "❌ Failed to add root folder '${MEDIA_SERIES_DIR}', HTTP ${status}" >&2
  fi
fi
unexpected_folders=$(echo "${rootfolders}" | jq -r '.[] | select(.path!="'"${MEDIA_SERIES_DIR}"'") | .path' | tr '\n' ' ')
if [[ -n "${unexpected_folders// /}" ]]; then
  echo "⚠️ Unexpected root folders present, remove by hand if unwanted [${unexpected_folders% }]"
fi
###############################################################################

###############################################################################
# Configure grab delay
###############################################################################
GRAB_DELAY_MIN=30
auth_header=(-H "X-Api-Key: ${SONARR_API_KEY}")
profile=$(curl -s "${SONARR_URL}/api/v3/delayprofile" "${auth_header[@]}" | jq '.[0]')
profile_id=$(echo "${profile}" | jq -r '.id')
profile_delay=$(echo "${profile}" | jq -r '.usenetDelay')
if [[ "${profile_delay}" == "${GRAB_DELAY_MIN}" ]]; then
  echo "✅ Usenet delay already ${GRAB_DELAY_MIN} min"
else
  updated_profile=$(echo "${profile}" | jq '.usenetDelay = '"${GRAB_DELAY_MIN}"'')
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT "${SONARR_URL}/api/v3/delayprofile/${profile_id}" \
    "${auth_header[@]}" -H "Content-Type: application/json" \
    -d "${updated_profile}")
  if [[ "${status}" == 2* ]]; then
    echo "✅ Usenet delay updated to ${GRAB_DELAY_MIN} min"
  else
    echo "❌ Failed to update usenet delay (HTTP ${status})"
  fi
fi
###############################################################################

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

MESSAGE="Waiting for service to start executing ... "
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkexecuting.sh"; do
  echo "${MESSAGE}" && sleep 1
done
echo "----------" && echo "✅ Service has started"