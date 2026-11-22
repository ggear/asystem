/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  { HEALTHCHECK_TOPIC="vernemq/health/live/$$/${RANDOM}";
  { for _ in 1 2 3 4 5 6 7 8; do sleep 0.5; timeout 2 mosquitto_pub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t "${HEALTHCHECK_TOPIC}" -m "ok" >/dev/null 2>&1; done; } & HEALTHCHECK_PUBLISHER=$!;
  HEALTHCHECK_RECEIVED="$(timeout 5 mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t "${HEALTHCHECK_TOPIC}" -C 1 2>/dev/null)";
  kill "${HEALTHCHECK_PUBLISHER}" 2>/dev/null;
  [[ "${HEALTHCHECK_RECEIVED}" == "ok" ]]; }
