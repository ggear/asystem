printf 'Entity Metadata publish script [zigbee2mqtt] restarting the service to republish its discovery topics:\n'
if docker restart zigbee2mqtt >/dev/null 2>&1; then
  printf 'zigbee2mqtt\n\nEntity Metadata publish script [zigbee2mqtt] waiting for the service to come up ... ' && sleep 30 && printf 'done\n'
else
  printf '\nEntity Metadata publish script [zigbee2mqtt] restart failed, the service is not running on this host\n' >&2
fi

DISCOVERED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'homeassistant/#' -W 5 2>/dev/null | grep -c '/0x' || true)
printf '\nEntity Metadata publish script [zigbee2mqtt] rediscovered [%s] devices\n\n' "${DISCOVERED}"
