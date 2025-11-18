/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  timeout 5 mosquitto_pub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t "vernemq/health/check" -m "ok" -r >/dev/null 2>&1 &&
  timeout 5 mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t "vernemq/health/check" -C 1 >/dev/null 2>&1
