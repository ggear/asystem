# Defines the entire ASystem backup process accross all modules intalled on this host,
# through the HOT, WARM and COLD paths, as implemented in backup_written.
#
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

backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "log" || return 1

  #TODO: Implement HOT path

  #TODO: Implement WARM path

  #TODO: Implement COLD path

  #TODO: Implement a json description of backup process broken down by HOT/WARM agrgegate and per module and COLD aggregate paths, with success/failure and timings
  echo "WARN: Backup not implemented, writing a placeholder [${BACKUP_MODULE_NAME}]" >&2
  echo "TODO: Provide implementation" >"${BACKUP_TARGET_PATH}.tmp"
  return 0
}
