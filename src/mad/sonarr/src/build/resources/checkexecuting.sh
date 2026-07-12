/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -s -w '%{http_code}' -o >(jq -e 'length == 0' >/dev/null) "http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/health" -H "X-Api-Key: ${SONARR_API_KEY}" | grep -q '^200$'
