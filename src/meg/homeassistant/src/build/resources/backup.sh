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

HOMEASSISTANT_BACKUP_LIVE="atomic"
HOMEASSISTANT_BACKUP_INCLUDES=(
  ".storage"
  "blueprints"
  "custom_templates"
)
HOMEASSISTANT_BACKUP_EXCLUDES=(
  ".HA_VERSION"
  ".cache"
  ".cloud"
  ".google_service_account.json"
  ".ha_run.lock"
  ".storage/*.bak-*"
  ".storage/*.migration_backup"
  ".storage/tmp*"
  "automations.yaml"
  "bootstrap.sh"
  "checkalive.sh"
  "checkexecuting.sh"
  "checkhealthy.sh"
  "configuration.yaml"
  "custom_components"
  "custom_config"
  "custom_packages"
  "customise.yaml"
  "deps"
  "hass-entities.yaml"
  "healthcheck.sh"
  "home-assistant.log*"
  "ip_bans.yaml"
  "network_devices.json"
  "tts"
  "ui-lovelace*"
  "www"
)

backup_versioned() { printf '%s\n' "${BACKUP_VERSIONED_NONE}"; }

backup_written() {
  backup_files "." HOMEASSISTANT_BACKUP_INCLUDES HOMEASSISTANT_BACKUP_EXCLUDES
}
