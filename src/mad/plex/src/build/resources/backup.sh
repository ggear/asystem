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

plex_backup_stopped() {
  local reported
  if reported="$(docker stop "${PLEX_BACKUP_CONTAINER}" 2>&1)"; then
    docker wait "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "Stop failed [${PLEX_BACKUP_CONTAINER}] [${reported}], copying the running configuration" >&2
  fi
}

backup_versioned() {
  docker exec "${BACKUP_MODULE_NAME}" "/usr/lib/plexmediaserver/Plex Media Server" --version
}

backup_written() {
  local status=0
  plex_backup_stopped
  backup_files "${PLEX_BACKUP_CONFIG}" PLEX_BACKUP_INCLUDES PLEX_BACKUP_EXCLUDES || status=1
  return "${status}"
}
