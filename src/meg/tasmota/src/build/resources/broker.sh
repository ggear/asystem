printf 'Entity Metadata publish script [tasmota] restarting devices to republish their retained state:\n'
DEVICES=()
while IFS= read -r DEVICE; do
  DEVICES+=("${DEVICE}")
done < <(find "$ROOT_DIR" -name "*.json" -exec grep -ho '"availability_topic": *"[^"]*"' {} + |
  cut -d'"' -f4 | cut -d/ -f3 | sort -u)
for DEVICE in "${DEVICES[@]}"; do
  printf '%s\n' "${DEVICE}"
  mosquitto_pub "${BROKER_ARGS[@]}" -t "tasmota/device/${DEVICE}/cmnd/Restart" -m "1"
done

printf '\nEntity Metadata publish script [tasmota] waiting for devices to boot ... ' && sleep 30 && printf 'done\n'

RESTARTED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'tasmota/device/+/tele/LWT' -W 5 2>/dev/null | sort -u | wc -l | tr -d ' ')
printf '\nEntity Metadata publish script [tasmota] restarted [%s] of [%d] devices\n\n' "${RESTARTED}" "${#DEVICES[@]}"
