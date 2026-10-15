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

PLEX_BACKUP_CONFIG="config"
PLEX_BACKUP_CONTAINER="${SERVICE_NAME:?}"
PLEX_BACKUP_SERVER="Library/Application Support/Plex Media Server"
PLEX_BACKUP_INCLUDES=(
  "${PLEX_BACKUP_SERVER}/Plug-in Support"
  "${PLEX_BACKUP_SERVER}/Preferences.xml"
)
PLEX_BACKUP_EXCLUDES=(
  "*.db-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
  "Caches"
  "${PLEX_BACKUP_SERVER}/.LocalAdminToken"
  "${PLEX_BACKUP_SERVER}/Cache"
  "${PLEX_BACKUP_SERVER}/Codecs"
  "${PLEX_BACKUP_SERVER}/Crash Reports"
  "${PLEX_BACKUP_SERVER}/Diagnostics"
  "${PLEX_BACKUP_SERVER}/Drivers"
  "${PLEX_BACKUP_SERVER}/Logs"
  "${PLEX_BACKUP_SERVER}/Media"
  "${PLEX_BACKUP_SERVER}/Metadata"
  "${PLEX_BACKUP_SERVER}/Plug-ins"
  "${PLEX_BACKUP_SERVER}/Scanners"
  "${PLEX_BACKUP_SERVER}/Setup Plex.html"
  "${PLEX_BACKUP_SERVER}/Updates"
  "${PLEX_BACKUP_SERVER}/plexmediaserver.pid"
)

PLEX_BACKUP_FAULT=0
PLEX_BACKUP_RESTART_TRIES=5
PLEX_BACKUP_RESTART_WAIT=10

plex_backup_stopped() {
  local reported
  if reported="$(docker stop "${PLEX_BACKUP_CONTAINER}" 2>&1)"; then
    docker wait "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "Stop failed [${PLEX_BACKUP_CONTAINER}] [${reported}], copying the running configuration" >&2
  fi
}

plex_backup_started() {
  [ "${BACKUP_SERVICE_RESTART}" = "true" ] || return 0
  local reported attempt=1
  while :; do
    if reported="$(docker start "${PLEX_BACKUP_CONTAINER}" 2>&1)"; then
      PLEX_BACKUP_FAULT=0
      [ "${attempt}" -gt 1 ] && echo "Started [${PLEX_BACKUP_CONTAINER}] on attempt [${attempt}]" >&2
      return 0
    fi
    echo "Start failed [${PLEX_BACKUP_CONTAINER}] [${reported}] on attempt [${attempt}] of [${PLEX_BACKUP_RESTART_TRIES}]" >&2
    [ "${attempt}" -lt "${PLEX_BACKUP_RESTART_TRIES}" ] || break
    attempt=$(( attempt + 1 ))
    sleep "${PLEX_BACKUP_RESTART_WAIT}"
  done
  PLEX_BACKUP_FAULT=1
  return 1
}

backup_interrupted() {
  plex_backup_started
}

backup_completed() {
  return "${PLEX_BACKUP_FAULT}"
}

backup_written() {
  local status=0
  plex_backup_stopped
  backup_files "${PLEX_BACKUP_CONFIG}" PLEX_BACKUP_INCLUDES PLEX_BACKUP_EXCLUDES || status=1
  plex_backup_started || true
  return "${status}"
}
