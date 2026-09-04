WRANGLE_BACKUP_HISTORY="data/history_adhoc.json:data/history_daily.json:data/history_raw.json"

backup_written() {
  backup_files "${WRANGLE_BACKUP_HISTORY}"
}
