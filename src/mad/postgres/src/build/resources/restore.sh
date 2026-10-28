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
  restore_report "would drop each database the dump names, then load the cluster dump into a running [${RESTORE_MODULE_NAME}]"
  restore_report "with the existing [postgres] role line removed and the TimescaleDB catalog loaded between [timescaledb_pre_restore] and [timescaledb_post_restore]"
  restore_report "set [POSTGRES_RESTORE_TIMESCALEDB_VERSION] to the extension version the dump was taken at when it differs from the image's, which is the case for a dump taken before the extension update"
  restore_report "the wrangle database is not in the dump and is rebuilt by wrangle, and the Home Assistant recorder's"
  restore_report "states, events and short term statistics come back empty, only their schema is dumped"
}

POSTGRES_RESTORE_SCRATCH="${RESTORE_MODULE_NAME}_restore"
POSTGRES_RESTORE_PORT="${POSTGRES_RESTORE_PORT:-15433}"
POSTGRES_RESTORE_TIMESCALEDB_VERSION="${POSTGRES_RESTORE_TIMESCALEDB_VERSION:-}"

postgres_restore_stream() {
  gzip -dc "${RESTORE_SOURCE_FILE}" | awk -v version="${POSTGRES_RESTORE_TIMESCALEDB_VERSION}" '
    /^CREATE ROLE postgres;$/ { next }
    /^CREATE EXTENSION IF NOT EXISTS timescaledb / {
      if (version != "") sub(/WITH SCHEMA public/, "WITH SCHEMA public VERSION \047" version "\047")
      print
      print "SELECT public.timescaledb_pre_restore();"
      pending = 1
      next
    }
    /^\\connect / {
      if (pending) print "SELECT public.timescaledb_post_restore();"
      pending = 0
    }
    { print }
    END { if (pending) print "SELECT public.timescaledb_post_restore();" }'
}

postgres_restore_databases() {
  gzip -dc "${RESTORE_SOURCE_FILE}" | sed -n 's/^CREATE DATABASE \([^ ]*\) .*/\1/p'
}

postgres_restore_loaded() {
  local container="${1}" user="${2}" database
  for database in postgres template1; do
    docker exec --user root "${container}" psql -U "${user}" -d "${database}" -v ON_ERROR_STOP=1 -qc "DROP EXTENSION IF EXISTS timescaledb CASCADE" >/dev/null || return 1
  done
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root "${container}" psql -U "${user}" -d postgres -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS \"${database}\" WITH (FORCE)" >/dev/null || return 1
  done < <(postgres_restore_databases)
  postgres_restore_stream | docker exec --interactive --user root "${container}" psql -U "${user}" -d postgres -v ON_ERROR_STOP=1 -q >/dev/null
}

backup_fingerprinted() {
  local container="${1:-${RESTORE_MODULE_NAME}}" user database
  user="postgres"
  [ "${container}" = "${RESTORE_MODULE_NAME}" ] && user="${POSTGRES_USER:?}"
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root "${container}" psql -U "${user}" -d "${database}" -Atc "
      SELECT '${database}.' || schemaname || '.' || tablename || ' ' ||
        (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', schemaname, tablename), false, true, '')))[1]::text
      FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1" || return 1
  done < <(docker exec --user root "${container}" psql -U "${user}" -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname") | sort
}

restore_staged() {
  local image scratch waited=0
  scratch="$(restore_scratch_dir)"
  image="$(docker inspect "${RESTORE_MODULE_NAME}" --format '{{.Config.Image}}')" || return 1
  rm -rf "${scratch}"
  mkdir -p "${scratch}" || return 1
  docker rm -f "${POSTGRES_RESTORE_SCRATCH}" >/dev/null 2>&1
  docker run --detach --name "${POSTGRES_RESTORE_SCRATCH}" --publish "127.0.0.1:${POSTGRES_RESTORE_PORT}:5432" \
    --env POSTGRES_PASSWORD=scratch --env POSTGRES_USER=postgres --volume "${scratch}:/var/lib/postgresql" \
    "${image}" >/dev/null || return 1
  until docker exec "${POSTGRES_RESTORE_SCRATCH}" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do
    waited=$((waited + 1))
    [ "${waited}" -le 180 ] || { restore_fault "scratch [${POSTGRES_RESTORE_SCRATCH}] did not accept connections within [180] seconds"; return 1; }
    sleep 1
  done
  postgres_restore_loaded "${POSTGRES_RESTORE_SCRATCH}" postgres || {
    restore_fault "could not load [${RESTORE_SOURCE_FILE}] into scratch [${POSTGRES_RESTORE_SCRATCH}]"
    return 1
  }
  printf '%s\n' "${POSTGRES_RESTORE_SCRATCH}"
}

restore_sealed() {
  local database failed=0
  while read -r database; do
    [ -n "${database}" ] || continue
    docker exec --user root --env PGOPTIONS="-c default_transaction_read_only=off" "${POSTGRES_RESTORE_SCRATCH}" \
      psql -U postgres -d postgres -v ON_ERROR_STOP=1 -qc "ALTER DATABASE \"${database}\" SET default_transaction_read_only = on" >/dev/null || failed=1
  done < <(docker exec --user root "${POSTGRES_RESTORE_SCRATCH}" psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn")
  return "${failed}"
}

restore_teardown() {
  docker rm -f "${POSTGRES_RESTORE_SCRATCH}" >/dev/null 2>&1
  rm -rf "$(restore_scratch_dir)"
}

restore_applied() {
  postgres_restore_loaded "${RESTORE_MODULE_NAME}" "${POSTGRES_USER:?}" || {
    restore_fault "could not load the cluster dump into [${RESTORE_MODULE_NAME}]"
    return 1
  }
  restore_changed "loaded the cluster dump into [${RESTORE_MODULE_NAME}]"
}
