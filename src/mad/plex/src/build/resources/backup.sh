# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path, overridable to back up another version's
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this
#
# Plex holds its plug-in databases open, so the service is stopped for the copy and restarted
# afterwards, whether the copy worked or not, both through install.sh rather than docker directly. Paths inside the tar are relative
# to the config directory, so a restore is:
#
#   tar --extract --gzip --file <backup>.tar.gz --directory ${BACKUP_SOURCE_PATH}/config

PLEX_BACKUP_CONFIG="config"
PLEX_BACKUP_INCLUDE="Library/Application Support/Plex Media Server/Plug-in Support"
PLEX_BACKUP_INSTALL="/var/lib/asystem/install/plex/latest/install.sh"

backup_written() {
  local status=0
  if [ ! -d "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}/${PLEX_BACKUP_INCLUDE}" ]; then
    echo "Declared path [${PLEX_BACKUP_INCLUDE}] is absent from [${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}]" >&2
    return 1
  fi
  backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
  "${PLEX_BACKUP_INSTALL}" stop >/dev/null || echo "Stop failed [${PLEX_BACKUP_INSTALL}], copying the running configuration" >&2
  tar --create --directory "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}" --numeric-owner --preserve-permissions \
    --file - -- "${PLEX_BACKUP_INCLUDE}" 2>/dev/null | gzip >"${BACKUP_TARGET_PATH}.tmp" || status=1
  "${PLEX_BACKUP_INSTALL}" restart >/dev/null || echo "Restart failed [${PLEX_BACKUP_INSTALL}]" >&2
  return "${status}"
}
