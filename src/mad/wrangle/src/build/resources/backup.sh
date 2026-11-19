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

WRANGLE_BACKUP_INCLUDES=(
  "data/bank"
  "data/history_adhoc.json"
  "data/history_daily.json"
  "data/history_raw.json"
)
WRANGLE_BACKUP_EXCLUDES=(
  "data/currency"
  "data/equity"
  "data/interest"
  "data/wrangle-run.lock"
)

WRANGLE_BACKUP_LOCK_SECONDS=600

backup_versioned() { printf '%s\n' "${BACKUP_VERSIONED_NONE}"; }

backup_written() {
  local wrangle_lock_path="${BACKUP_SOURCE_PATH:?}/data/wrangle-run.lock" wrangle_lock_fd wrangle_status
  exec {wrangle_lock_fd}>>"${wrangle_lock_path}" || return 1
  if ! flock -w "${WRANGLE_BACKUP_LOCK_SECONDS}" "${wrangle_lock_fd}"; then
    echo "Run lock [${wrangle_lock_path}] not acquired within [${WRANGLE_BACKUP_LOCK_SECONDS}] seconds, not copying mid run" >&2
    exec {wrangle_lock_fd}>&-
    return 1
  fi
  backup_files "." WRANGLE_BACKUP_INCLUDES WRANGLE_BACKUP_EXCLUDES
  wrangle_status=$?
  exec {wrangle_lock_fd}>&-
  return "${wrangle_status}"
}
