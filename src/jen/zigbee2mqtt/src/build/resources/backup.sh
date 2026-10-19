# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, checks the archive's integrity, renames the temporary file on success, prunes and
# sets the exit code. Define backup_written below, naming the backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". A snippet copying files passes
# backup_files a root under BACKUP_SOURCE_PATH and the names of its include and exclude arrays, an
# absent include fails the backup and whatever under the root neither array covers is reported. A
# snippet leaving the estate changed while it works, such as one stopping its own container, also
# defines backup_interrupted, called on INT, TERM or HUP but never on a backup that merely fails, and
# backup_completed, called once the archive has been named and kept whatever the outcome, whose
# non-zero return fails the run without discarding the archive. Never assign another wrapper
# variable, prefix this snippet's own state with the module name, and expand a value read from .env
# as "${VAR:?}", so a missing key fails by name rather than corrupting the backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

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
