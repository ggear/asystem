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
# Configure library root folder
###############################################################################
MEDIA_SERIES_DIR="/library"
rootfolders=$(curl -s "${SONARR_URL}/api/v3/rootfolder" -H "X-Api-Key: ${SONARR_API_KEY}")
echo "${rootfolders}" | jq -c '.[]' | while read -r folder; do
  id=$(echo "${folder}" | jq -r '.id')
  status=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${SONARR_URL}/api/v3/rootfolder/${id}" \
    -H "X-Api-Key: ${SONARR_API_KEY}")
  if [[ "${status}" -eq 200 ]]; then
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

if [[ "${status}" -eq 201 ]]; then
  echo "✅ Successfully added root folder '${MEDIA_SERIES_DIR}'"
else
  echo "❌ Failed to add root folder '${MEDIA_SERIES_DIR}', HTTP ${status}" >&2
fi
###############################################################################

###############################################################################
# Configure indexer
###############################################################################
indexers_json=$(curl -s "${SONARR_URL}/api/v3/indexer" -H "X-Api-Key: ${SONARR_API_KEY}")
exists=$(echo "${indexers_json}" | jq -e '.[] | select(.name=="NZBgeek")' >/dev/null 2>&1 && echo "yes" || echo "no")
if [[ "${exists}" == "yes" ]]; then
  echo "✅ Indexer NZBgeek already exists"
else
  echo "➕ Adding indexer NZBgeek"
  payload=$(jq -n --arg n "NZBgeek" --arg k "${GEEK_KEY}" --arg u "https://api.nzbgeek.info/api" \
    '{enableRss: true, enableSearch: true, name: $n, implementation: "Newznab", configContract: "NewznabSettings", settings: {apiUrl: $u, apiKey: $k, categories: "5000,5040,5070"}}')
  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${SONARR_URL}/api/v3/indexer" \
    -d "${payload}" \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json")

  if [[ "${response}" == "201" ]]; then
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
  echo "➕ Adding download client SABnzbd"
  sab_payload=$(jq -n \
    '{name: "SABnzbd", enabled: true, protocol: "sabnzbd", host: "localhost", port: 8080, apiKey: "", username: "", password: "", category: "tv", recentPriority: 1, priority: 1, useSsl: false, tvCategory: "tv"}')

  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${SONARR_URL}/api/v3/downloadclient" \
    -d "${sab_payload}" \
    -H "X-Api-Key: ${SONARR_API_KEY}" \
    -H "Content-Type: application/json")

  if [[ "${response}" == "201" ]]; then
    echo "✅ Added download client SABnzbd"
  else
    echo "❌ Failed to add download client SABnzbd (HTTP ${response})"
  fi
fi
###############################################################################

###############################################################################
# Configure H265 prefered custom format
###############################################################################
customformat_name="Prefer H265"
customformat_exists=$(curl -s "${SONARR_URL}/api/v3/customFormat" -H "X-Api-Key: ${SONARR_API_KEY}" | jq -e --arg name "${customformat_name}" '.[] | select(.name == $name)' >/dev/null 2>&1 && echo "yes" || echo "no")
if [[ "${customformat_exists}" == "yes" ]]; then
  customformat_id=$(curl -s "${SONARR_URL}/api/v3/customFormat" -H "X-Api-Key: ${SONARR_API_KEY}" | jq -r --arg name "${customformat_name}" '.[] | select(.name == $name) | .id')
else
  payload=$(jq -n --arg name "${customformat_name}" '{
    name: $name,
    includeCustomFormatWhenRenaming: true,
    specifications: [
      {
        name: "Must contain",
        required: true,
        implementation: "MustContainSpecification",
        negated: false,
        terms: [
          { term: "265" }
        ]
      }
    ]
  }')
  response=$(curl -s -w "%{http_code}" -o /tmp/cf_response.json -X POST "${SONARR_URL}/api/v3/customFormat" -d "${payload}" -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json")
  http_code="${response: -3}"
  if [[ "${http_code}" == "201" ]]; then
    customformat_id=$(jq -r '.id' /tmp/cf_response.json)
    echo "✅ Found custom format"
  else
    echo "❌ Failed to find custom format"
  fi
fi
quality_profiles=$(curl -s "${SONARR_URL}/api/v3/qualityprofile" -H "X-Api-Key: ${SONARR_API_KEY}")
echo "${quality_profiles}" | jq -c '.[]' | while read -r profile; do
  profile_id=$(echo "${profile}" | jq -r '.id')
  profile_name=$(echo "${profile}" | jq -r '.name')
  current_cfs=$(echo "${profile}" | jq '.customFormats // []')
  cf_ids=$(echo "${current_cfs}" | jq -r '.[].id' 2>/dev/null || echo "")
  has_cf="false"
  for id in ${cf_ids}; do
    if [[ "${id}" == "${customformat_id}" ]]; then
      has_cf="true"
      break
    fi
  done
  if [[ "${has_cf}" == "false" ]]; then
    updated_cfs=$(echo "${current_cfs}" | jq --argjson id "${customformat_id}" '. + [{"id": $id, "score": 100}]')
    updated_profile=$(echo "${profile}" | jq --argjson cfs "${updated_cfs}" '.customFormats = $cfs')
    response=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${SONARR_URL}/api/v3/qualityprofile/${profile_id}" -d "${updated_profile}" -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json")
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
echo "----------" && echo "Service has started"