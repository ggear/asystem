[ "$(curl "$INFLUXDB3_HOST_URL/health" --header "Authorization: Bearer $INFLUXDB3_AUTH_TOKEN")" == "OK" ]
