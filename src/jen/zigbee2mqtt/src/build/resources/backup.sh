# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this

backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "zip" || return 1
  docker exec -i --user root "${BACKUP_MODULE_NAME}" bash -c '
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
