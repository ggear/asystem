
curl -sf -X GET http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}"

#curl -X POST http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d '
#  {
#    "name": "NZBgeek",
#    "enableRss": true,
#    "enableAutomaticSearch": true,
#    "enableInteractiveSearch": true,
#    "supportsRss": true,
#    "supportsSearch": true,
#    "protocol": "usenet",
#    "priority": 25,
#    "implementation": "Newznab",
#    "configContract": "NewznabSettings",
#    "tags": [],
#    "fields": [
#      {
#        "name": "baseUrl",
#        "value": "https://api.nzbgeek.info"
#      },
#      {
#        "name": "apiKey",
#        "value": "'"${GEEK_KEY}"'"
#      }
#    ]
#  }
#'
