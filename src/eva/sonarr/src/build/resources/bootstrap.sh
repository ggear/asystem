MEDIA_INDEX_MAX=5
MEDIA_CATEGORIES=("docos" "parents" "kids" "comedy")
MEDIA_DIRS=()

for share_num in $(seq 1 ${MEDIA_INDEX_MAX}); do
  for category in "${MEDIA_CATEGORIES[@]}"; do
    MEDIA_DIRS+=("/share/${share_num}/media/${category}/series")
  done
done

existing_json=$(curl -s "${SONARR_URL}/api/v3/rootfolder" -H "X-Api-Key: ${SONARR_API_KEY}")
existing_paths=$(echo "${existing_json}" | jq -r '.[].path')

for desired_path in "${MEDIA_DIRS[@]}"; do
  found="no"
  while IFS= read -r existing_path; do
    if [[ "${existing_path}" == "${desired_path}" ]]; then
      found="yes"
      break
    fi
  done <<< "${existing_paths}"

  if [[ "${found}" == "yes" ]]; then
    echo "✅ Root folder already exists: ${desired_path}"
  else
    echo "➕ Adding root folder: ${desired_path}"
    payload="{\"path\": \"${desired_path}\", \"accessible\": true}"

    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      "${SONARR_URL}/api/v3/rootfolder" \
      -d "${payload}" \
      -H "X-Api-Key: ${SONARR_API_KEY}" \
      -H "Content-Type: application/json")

    if [[ "${response}" == "201" ]]; then
      echo "✅ Added root folder: ${desired_path}"
    else
      echo "❌ Failed to add root folder: ${desired_path} (HTTP ${response})"
    fi
  fi
done

echo "${existing_json}" | jq -c '.[]' | while read -r folder; do
  folder_path=$(echo "${folder}" | jq -r '.path')
  folder_id=$(echo "${folder}" | jq -r '.id')

  keep="no"
  for desired in "${MEDIA_DIRS[@]}"; do
    if [[ "${desired}" == "${folder_path}" ]]; then
      keep="yes"
      break
    fi
  done

  if [[ "${keep}" == "no" ]]; then
    echo "❌ Removing unused root folder: ${folder_path}"
    response=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
      "${SONARR_URL}/api/v3/rootfolder/${folder_id}" \
      -H "X-Api-Key: ${SONARR_API_KEY}")

    if [[ "${response}" == "200" ]]; then
      echo "✅ Removed root folder: ${folder_path}"
    else
      echo "❌ Failed to remove root folder: ${folder_path} (HTTP ${response})"
    fi
  fi
done

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
  else
    exit 1
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
