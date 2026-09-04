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

INFLUXDB3_RESTORE_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_RESTORE_STORE="${RESTORE_SOURCE_PATH}/${INFLUXDB3_RESTORE_CLUSTER}/backups"

influxdb3_restore_named() {
  local root
  root="$(tar -tzf "${RESTORE_SOURCE_FILE}" 2>/dev/null | head -1)"
  printf '%s\n' "${root%%/*}"
}

influxdb3_restore_parent() {
  local fulls
  mapfile -t fulls < <(find "${INFLUXDB3_RESTORE_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^full-' | sort)
  [ "${#fulls[@]}" -eq 1 ] || return 1
  printf '%s\n' "${fulls[0]}"
}

restore_planned() {
  local name parent
  name="$(influxdb3_restore_named)"
  case "${name}" in
  delta-*)
    parent="$(influxdb3_restore_parent)" || {
      restore_report "would need exactly one full backup already in [${INFLUXDB3_RESTORE_STORE}] to place [${name}] under, restore its full first"
      return 0
    }
    restore_report "would extract [${name}] into [${INFLUXDB3_RESTORE_STORE}/${parent}/incremental] and run [influxdb3 create restore --backup ${name}]"
    ;;
  *)
    restore_report "would extract [${name}] into [${INFLUXDB3_RESTORE_STORE}] and run [influxdb3 create restore --backup ${name}]"
    ;;
  esac
}

restore_applied() {
  local name parent target
  name="$(influxdb3_restore_named)"
  [ -n "${name}" ] || { restore_fault "could not read the backup name out of [${RESTORE_SOURCE_FILE}]"; return 1; }
  case "${name}" in
  delta-*)
    parent="$(influxdb3_restore_parent)" || {
      restore_fault "need exactly one full backup in [${INFLUXDB3_RESTORE_STORE}] to place [${name}] under, restore its full first"
      return 1
    }
    target="${INFLUXDB3_RESTORE_STORE}/${parent}/incremental"
    ;;
  *) target="${INFLUXDB3_RESTORE_STORE}" ;;
  esac
  mkdir -p "${target}"
  tar --extract --gzip --directory "${target}" --file "${RESTORE_SOURCE_FILE}" || {
    restore_fault "could not extract [${RESTORE_SOURCE_FILE}] into [${target}]"
    return 1
  }
  restore_changed "extracted [${name}] into [${target}]"
  docker exec --user root "${RESTORE_MODULE_NAME}" influxdb3 create restore --backup "${name}" || {
    restore_fault "could not restore [${name}] into [${RESTORE_MODULE_NAME}]"
    return 1
  }
  restore_changed "restored [${name}] into [${RESTORE_MODULE_NAME}]"
}
