backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "zip" || return 1
  docker exec -i --user root "${BACKUP_MODULE_NAME}" bash -c '
set -o pipefail
response=$(mktemp)
trap "rm -f ${response}" EXIT
mosquitto_sub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/response/backup -C 1 -W 60 >"${response}" 2>/dev/null &
subscriber=$!
sleep 1
mosquitto_pub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/request/backup -m "{}" 2>/dev/null || exit 1
wait "${subscriber}" 2>/dev/null
[ "$(jq -r ".status // empty" "${response}" 2>/dev/null)" = "ok" ] || exit 1
jq -r ".data.zip // empty" "${response}" | base64 -d
  ' >"${BACKUP_TARGET_PATH}.tmp"
}
