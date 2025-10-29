curl -s -o /dev/null -w "%{http_code}" "${ZIGBEE2MQTT_SERVICE}:${ZIGBEE2MQTT_HTTP_PORT}" | grep -q '^200$'
