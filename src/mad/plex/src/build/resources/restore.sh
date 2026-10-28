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
RESTORE_SERVICE_STATE="stopped"

PLEX_RESTORE_CONFIG="config"
PLEX_RESTORE_SERVER="Library/Application Support/Plex Media Server"
RESTORE_CARRY=("*.db-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]")

restore_planned() {
  restore_report "would stop [${RESTORE_MODULE_NAME}], extract the Plex configuration into [${RESTORE_SOURCE_PATH}/${PLEX_RESTORE_CONFIG}] and start it again"
}

restore_applied() {
  restore_files "${PLEX_RESTORE_SERVER}/Plug-in Support:${PLEX_RESTORE_SERVER}/Preferences.xml" "${RESTORE_SOURCE_PATH}/${PLEX_RESTORE_CONFIG}"
}

restore_checked() {
  local scratch="${1}" image database result failed=0
  image="$(docker inspect "${RESTORE_MODULE_NAME}" --format '{{.Config.Image}}')" || return 1
  for database in "${scratch}/${PLEX_RESTORE_SERVER}/Plug-in Support/Databases/"*.db; do
    [ -f "${database}" ] || continue
    result="$(docker run --rm --network none --volume "${scratch}:/scratch" --entrypoint "/usr/lib/plexmediaserver/Plex SQLite" \
      "${image}" "/scratch/${database#"${scratch}/"}" "PRAGMA integrity_check" 2>&1)"
    if [ "${result}" != "ok" ]; then
      restore_fault "integrity_check of [$(basename "${database}")] answered [$(printf '%s' "${result}" | head -n 1)]"
      failed=1
    else
      restore_report "check [$(basename "${database}")] integrity_check ok"
    fi
  done
  return "${failed}"
}
