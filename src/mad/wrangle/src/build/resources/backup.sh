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
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this and came from the same version
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

WRANGLE_BACKUP_HISTORY="data/history_adhoc.json:data/history_daily.json:data/history_raw.json"

backup_written() {
  backup_files "${WRANGLE_BACKUP_HISTORY}"
}
