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

HOMEASSISTANT_RESTORE_PATHS=".storage:blueprints:custom_templates"

restore_planned() {
  restore_report "would stop [${RESTORE_MODULE_NAME}], extract [${HOMEASSISTANT_RESTORE_PATHS}] into [${RESTORE_SOURCE_PATH}] and start it again"
}

restore_applied() {
  restore_files "${HOMEASSISTANT_RESTORE_PATHS}"
}
