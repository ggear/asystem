# The engine (`supervisor backup restore`) owns the run, this snippet owns the restore, as hooks each in its own bash.
# Define restore_applied, writing "${RESTORE_SOURCE_FILE}" back into the service, and declare RESTORE_SERVICE_STATE.
# Optional hooks: restore_planned, restore_staged, restore_sealed, restore_teardown, restore_checked, restore_merged,
# restore_settled.
# No hook relies on a variable another set, own state is prefixed with the module name, .env values expand as "${VAR:?}".
#
# RESTORE_MODULE_NAME     this module's name
# RESTORE_SOURCE_PATH     this module's data path, the restore target
# RESTORE_SOURCE_FILE     the artefact being restored
# RESTORE_CHAIN_FILES     every artefact of the chain, oldest first
# RESTORE_RUN_TIMESTAMP   the timestamp of the run the artefact belongs to
# RESTORE_FULL_SUFFIX     suffix of a full backup
# RESTORE_DELTA_SUFFIX    suffix of a delta backup
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
    result="$(docker run --rm --name "${RESTORE_MODULE_NAME}_restore" --network none --volume "${scratch}:/scratch" --entrypoint "/usr/lib/plexmediaserver/Plex SQLite" \
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
