/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  NOW=$(awk '{printf "%d", $1 * 1000}' "${RACKMAINS_UPTIME_FILE:-/proc/uptime}") &&
  LIVENESS=$(cat "${RACKMAINS_RUN_DIR:-/run/rackmains}/liveness.json") &&
  STALE=$(for KEY in boot_ms last_read_boot_ms guard_boot_ms; do STAMP=$(sed -n "s/.*\"${KEY}\":\([0-9]*\).*/\1/p" <<<"${LIVENESS}"); { [ -n "${STAMP}" ] && [ $((NOW - STAMP)) -lt 30000 ]; } || echo "${KEY}"; done) &&
  [ -z "${STALE}" ] &&
  ! grep -q '"ups_problem":true' <<<"${LIVENESS}"
