printf 'Entity Metadata publish script [zigbee2mqtt] waiting for the service to republish its discovery topics ... ' && sleep 15 && printf 'done\n'

DISCOVERED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'homeassistant/#' -W 5 2>/dev/null | grep -c '/0x' || true)
printf '\nEntity Metadata publish script [zigbee2mqtt] rediscovered [%s] devices\n\n' "${DISCOVERED}"
