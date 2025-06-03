if [ $(curl -sf -X GET http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}" | jq 'length == 1 and .[0].name == "NZBgeek"') != "true" ]; then
  curl -X POST http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d '
{
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
    {
      "name": "baseUrl",
      "value": "https://api.nzbgeek.info"
    },
    {
      "name": "apiKey",
      "value": "'"${GEEK_KEY}"'"
    }
  ]
}
  '
fi

if [ $(curl -sf -X GET http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/downloadclient -H "X-Api-Key: ${SONARR_API_KEY}" | jq 'length == 1 and .[0].name == "SABnzbd"') != "true" ]; then
  curl -X POST http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/downloadclient -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d '
{
  "name": "SABnzbd12",
  "enable": true,
  "protocol": "usenet",
  "priority": 1,
  "removeCompletedDownloads": true,
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
}
  '
fi
