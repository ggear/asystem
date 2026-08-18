# Defines backup_written for this module, naming its artifact with backup_target (or letting
# backup_files do both) and writing "${BACKUP_PUB_TARGET}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_PUB_MODULE       this module's name, and its container's name
# BACKUP_PUB_SOURCE       this module's data directory
# BACKUP_PUB_DIR          the backup directory inside it, where artifacts land
# BACKUP_PUB_STAMP        this run's timestamp, shared by the directory and the filename
# BACKUP_PUB_FULL         the suffix marking a self-contained artifact
# BACKUP_PUB_DELTA        the suffix marking an artifact that needs the full before it
# BACKUP_PUB_RETAIN_DAYS  the dense window, in days
# BACKUP_PUB_TARGET       this run's artifact path, empty until backup_target names it

backup_written() {
  backup_target "${BACKUP_PUB_FULL}" "zip" || return 1
  docker exec -i --user root "${BACKUP_PUB_MODULE}" bash -c '
response=$(mktemp)
trap "rm -f ${response}" EXIT
mosquitto_sub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/response/backup -C 1 -W 60 >"${response}" 2>/dev/null &
subscriber=$!
sleep 1
mosquitto_pub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/request/backup -m "{}" 2>/dev/null || exit 1
wait "${subscriber}" 2>/dev/null
[ "$(jq -r ".status // empty" "${response}" 2>/dev/null)" = "ok" ] || exit 1
jq -r ".data.zip // empty" "${response}" | base64 -d
  ' >"${BACKUP_PUB_TARGET}.tmp"
}
