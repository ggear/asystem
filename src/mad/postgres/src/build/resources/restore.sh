# The wrapper owns the run, this snippet owns the restore. The wrapper resolves the artifact, checks
# its integrity, takes a safety backup, stops or starts the service and sets the exit code. Define
# restore_applied below, reading "${RESTORE_SOURCE_FILE}" and writing it back into the service, and
# optionally restore_planned to describe that in the dry run. Declare RESTORE_SERVICE_STATE as
# "stopped" when the restore replaces files the service holds open, or "running" when it is applied
# through the service itself. Never assign another wrapper variable, prefix this snippet's own state
# with the module name, and expand a value read from .env as "${VAR:?}", so a missing key fails by
# name rather than corrupting the restore.
#
# RESTORE_MODULE_NAME     this module's name
# RESTORE_SOURCE_PATH     this module's data path, the restore target
# RESTORE_SOURCE_FILE     the artifact being restored from
# RESTORE_SOURCE_VERSION  the version the artifact was taken from
# RESTORE_RUN_TIMESTAMP   the timestamp of the run the artifact belongs to
# RESTORE_FULL_SUFFIX     the file suffix marking a full backup
# RESTORE_DELTA_SUFFIX    the file suffix marking a delta backup
# RESTORE_SERVICE_STATE   the state the service must be in, stopped or running
RESTORE_SERVICE_STATE="running"

restore_planned() {
  restore_report "would load the cluster dump into a running [${RESTORE_MODULE_NAME}], restoring roles and every database it names"
  restore_report "the dump carries TimescaleDB catalog data with circular foreign keys, so a database that already exists"
  restore_report "should be dropped first, or restored with [SELECT timescaledb_pre_restore()] and [timescaledb_post_restore()]"
}

restore_applied() {
  gzip -dc "${RESTORE_SOURCE_FILE}" | docker exec -i --user root "${RESTORE_MODULE_NAME}" \
    psql -U "${POSTGRES_USER:?}" -d postgres -v ON_ERROR_STOP=1 >/dev/null || {
    restore_fault "could not load the cluster dump into [${RESTORE_MODULE_NAME}]"
    return 1
  }
  restore_changed "loaded the cluster dump into [${RESTORE_MODULE_NAME}]"
}
