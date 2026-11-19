# The engine (`supervisor backup run`) owns the run, this snippet owns the backup, as hooks each in its own bash.
# Define backup_written, naming the target with backup_target or backup_files and writing "${BACKUP_TARGET_PATH}.tmp".
# Optional hooks: backup_interrupted, backup_completed, backup_pruned_store, backup_versioned.
# No hook relies on a variable another set, own state is prefixed with the module name, .env values expand as "${VAR:?}".
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's data path
# BACKUP_SOURCE_VERSION   the version being backed up
# BACKUP_TARGET_PATH      this run's artefact path, set by backup_target
# BACKUP_RUN_TIMESTAMP    this run's timestamp
# BACKUP_FULL_SUFFIX      suffix of a full backup
# BACKUP_DELTA_SUFFIX     suffix of a delta backup, which needs a full one before it
# BACKUP_VERSIONED_NONE   what backup_versioned prints when a restore needs no software version
# BACKUP_SKIP_HOURS       skip when the newest backup is younger than this, zero never skips

backup_versioned() { printf '%s\n' "${BACKUP_VERSIONED_NONE}"; }

backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "zip" || return 1
  docker exec -i --user root "${BACKUP_MODULE_NAME}" bash -c '
set -o pipefail
response=$(mktemp)
trap "rm -f ${response}" EXIT
for attempt in 1 2 3; do
  transaction="backup-$$-${attempt}"
  mosquitto_sub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/response/backup -C 1 -W 60 >"${response}" 2>/dev/null &
  subscriber=$!
  sleep "${attempt}"
  if mosquitto_pub -h "${VERNEMQ_SERVICE:?}" -p "${VERNEMQ_API_PORT:?}" -t zigbee/bridge/request/backup -m "{\"transaction\":\"${transaction}\"}" 2>/dev/null; then
    wait "${subscriber}" 2>/dev/null
    if [ "$(jq -r --arg transaction "${transaction}" "select(.transaction == \$transaction) | .status // empty" "${response}" 2>/dev/null)" = "ok" ]; then
      jq -r ".data.zip // empty" "${response}" | base64 -d
      exit
    fi
  else
    kill "${subscriber}" 2>/dev/null
    wait "${subscriber}" 2>/dev/null
  fi
  echo "Backup request [${transaction}] got no ok response, attempt [${attempt}/3]" >&2
done
exit 1
  ' >"${BACKUP_TARGET_PATH}.tmp"
}
