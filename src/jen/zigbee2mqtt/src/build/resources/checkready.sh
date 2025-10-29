/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ] &&
  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/groups' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ] &&
  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/devices' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ]
