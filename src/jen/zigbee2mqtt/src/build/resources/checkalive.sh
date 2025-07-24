[ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ]
