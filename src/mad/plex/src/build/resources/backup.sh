# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

PLEX_BACKUP_CONFIG="config"
PLEX_BACKUP_CONTAINER="${SERVICE_NAME:?}"
PLEX_BACKUP_INCLUDES=(
  "Library/Application Support/Plex Media Server/Plug-in Support"
  "Library/Application Support/Plex Media Server/Preferences.xml"
)
PLEX_BACKUP_EXCLUDES=(
  "*.db-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
  "Caches"
)

backup_written() {
  local status=0 include exclude excludes=()
  for include in "${PLEX_BACKUP_INCLUDES[@]}"; do
    if [ ! -e "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}/${include}" ]; then
      echo "Declared path [${include}] is absent from [${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}]" >&2
      return 1
    fi
  done
  for exclude in "${PLEX_BACKUP_EXCLUDES[@]}"; do
    excludes+=("--exclude=${exclude}")
  done
  backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
  if docker stop "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1; then
    docker wait "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "Stop failed [${PLEX_BACKUP_CONTAINER}], copying the running configuration" >&2
  fi
  tar --create --directory "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}" --numeric-owner --preserve-permissions \
    "${excludes[@]}" --file - -- "${PLEX_BACKUP_INCLUDES[@]}" 2>/dev/null | gzip >"${BACKUP_TARGET_PATH}.tmp" || status=1
  if [ "${BACKUP_SERVICE_RESTART}" = "true" ]; then
    docker start "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || echo "Start failed [${PLEX_BACKUP_CONTAINER}]" >&2
  fi
  return "${status}"
}
