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
  if [ "${INFLUXDB3_RESTORE_REPLACE:-false}" != "true" ] && [ -n "$(backup_fingerprinted "${RESTORE_LIVE_ADDRESS}" 2>/dev/null)" ]; then
    restore_fault "[${RESTORE_MODULE_NAME}] holds closed days a replace would discard, restore with [--mode=merge], or set [INFLUXDB3_RESTORE_REPLACE=true] to replace regardless"
    return 1
  fi
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

INFLUXDB3_RESTORE_DATABASE="${INFLUXDB3_DATABASE_HOME:-home}"
INFLUXDB3_RESTORE_SCRATCH="${RESTORE_MODULE_NAME}_restore"
INFLUXDB3_RESTORE_PORT="${INFLUXDB3_RESTORE_PORT:-18182}"
INFLUXDB3_RESTORE_CHUNK_BYTES="${INFLUXDB3_RESTORE_CHUNK_BYTES:-4194304}"
INFLUXDB3_RESTORE_WRITE_PAUSE="${INFLUXDB3_RESTORE_WRITE_PAUSE:-0}"
RESTORE_LIVE_ADDRESS="${RESTORE_MODULE_NAME}"

backup_fingerprinted() {
  docker exec --user root --interactive "${1:-${RESTORE_MODULE_NAME}}" bash -s <<'FINGERPRINT'
set -o pipefail
query() {
  influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME:?}" ${INFLUXDB3_TOKEN_HOME:+--token "${INFLUXDB3_TOKEN_HOME}"} "$1"
}
tables="$(query "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox' ORDER BY table_name" | jq -r '.[].table_name')" || exit 1
for table in ${tables}; do
  query "SELECT date_trunc('day', time) AS day, count(*) AS n FROM \"${table}\" WHERE time < date_trunc('day', now()) GROUP BY 1" |
    jq -r --arg table "${table}" '.[] | "\($table)/\(.day[0:10]) \(.n)"' || exit 1
done | sort
FINGERPRINT
}

influxdb3_restore_started() {
  local mode="${1:-}" image
  image="$(docker inspect "${RESTORE_MODULE_NAME}" --format '{{.Config.Image}}')" || return 1
  docker rm -f "${INFLUXDB3_RESTORE_SCRATCH}" >/dev/null 2>&1
  docker run --detach --name "${INFLUXDB3_RESTORE_SCRATCH}" --publish "127.0.0.1:${INFLUXDB3_RESTORE_PORT}:8181" \
    --volume "$(restore_scratch_dir):/asystem/mnt" --env "INFLUXDB3_DATABASE_HOME=${INFLUXDB3_RESTORE_DATABASE}" \
    --entrypoint influxdb3 "${image}" serve --node-id node_1 --cluster-id "${INFLUXDB3_RESTORE_CLUSTER}" --object-store file \
    --data-dir /asystem/mnt --license-type home --without-auth --disable-telemetry-upload ${mode:+--mode "${mode}"} >/dev/null || return 1
  local waited=0
  until curl -sf "http://127.0.0.1:${INFLUXDB3_RESTORE_PORT}/health" >/dev/null 2>&1; do
    waited=$((waited + 1))
    [ "${waited}" -le 120 ] || { restore_fault "scratch [${INFLUXDB3_RESTORE_SCRATCH}] did not answer health within [120] seconds"; return 1; }
    sleep 1
  done
}

influxdb3_restore_awaited() {
  local id="${1}" status="" waited=0 out
  while [ "${waited}" -lt 600 ]; do
    out="$(docker exec "${INFLUXDB3_RESTORE_SCRATCH}" influxdb3 status restore --id "${id}" 2>&1)"
    status="$(printf '%s\n' "${out}" | sed -n 's/^Status: *//p' | head -n 1)"
    case "${status}" in
    completed) return 0 ;;
    failed)
      restore_fault "restore [${id}] failed in [${INFLUXDB3_RESTORE_SCRATCH}]"
      return 1
      ;;
    esac
    waited=$((waited + 2))
    sleep 2
  done
  restore_fault "restore [${id}] did not complete within [600] seconds, last status [${status:-unknown}]"
  return 1
}

restore_staged() {
  local scratch file name full="" target id output
  scratch="$(restore_scratch_dir)"
  rm -rf "${scratch}"
  mkdir -p "${scratch}/${INFLUXDB3_RESTORE_CLUSTER}" || return 1
  cp -p "${RESTORE_INTERNAL_SOURCE_DIR}/${INFLUXDB3_RESTORE_CLUSTER}/trial_or_home_license" "${scratch}/${INFLUXDB3_RESTORE_CLUSTER}/" || {
    restore_fault "could not copy the home licence into scratch, a fresh licence would start email verification"
    return 1
  }
  restore_stamped staging "starting scratch container [${INFLUXDB3_RESTORE_SCRATCH}]"
  influxdb3_restore_started "" || return 1
  local step=0
  for file in "${RESTORE_CHAIN_FILES[@]}"; do
    step=$((step + 1))
    name="$(tar -tzf "${file}" 2>/dev/null | head -n 1)"
    name="${name%%/*}"
    case "${name}" in
    full-*)
      full="${name}"
      target="${scratch}/${INFLUXDB3_RESTORE_CLUSTER}/backups"
      ;;
    delta-*) target="${scratch}/${INFLUXDB3_RESTORE_CLUSTER}/backups/${full}/incremental" ;;
    *)
      restore_fault "cannot read a backup name out of [${file}]"
      return 1
      ;;
    esac
    restore_stamped staging "restoring [${name}] into scratch, step [${step}] of [${#RESTORE_CHAIN_FILES[@]}]"
    mkdir -p "${target}"
    tar --extract --gzip --directory "${target}" --file "${file}" || { restore_fault "could not extract [${file}] into scratch"; return 1; }
    output="$(docker exec "${INFLUXDB3_RESTORE_SCRATCH}" influxdb3 create restore --backup "${name}" 2>&1)" || {
      restore_fault "could not start the restore of [${name}] in scratch"
      return 1
    }
    id="$(printf '%s\n' "${output}" | sed -n 's/.*--id \([0-9a-f-]*\).*/\1/p' | head -n 1)"
    [ -n "${id}" ] || { restore_fault "no restore id in [${output}]"; return 1; }
    influxdb3_restore_awaited "${id}" || return 1
  done
  printf '%s\n' "${INFLUXDB3_RESTORE_SCRATCH}"
}

restore_sealed() {
  influxdb3_restore_started query
}

restore_teardown() {
  docker rm -f "${INFLUXDB3_RESTORE_SCRATCH}" >/dev/null 2>&1
  rm -rf "$(restore_scratch_dir)"
}

influxdb3_restore_niced() {
  if command -v ionice >/dev/null 2>&1; then
    nice -n 10 ionice -c 3 "$@"
  else
    nice -n 10 "$@"
  fi
}

influxdb3_restore_lp() {
  influxdb3_restore_niced python3 -c '
import json, sys
table = sys.argv[1]
types = json.loads(sys.argv[2])
tags = sorted(column for column, kind in types.items() if kind.startswith("Dictionary"))
def measurement(text): return text.replace(",", "\\,").replace(" ", "\\ ")
def key(text): return text.replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")
def string(text): return text.replace("\\", "\\\\").replace("\"", "\\\"")
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    row = json.loads(raw)
    stamp = row.pop("time_ns")
    row.pop("time", None)
    series = "".join(",%s=%s" % (key(column), key(str(row[column]))) for column in tags if row.get(column) not in (None, ""))
    fields = []
    for column, value in row.items():
        if column in tags or value is None:
            continue
        kind = types.get(column, "")
        if kind == "Boolean":
            fields.append("%s=%s" % (key(column), "true" if value else "false"))
        elif kind.startswith("UInt"):
            fields.append("%s=%du" % (key(column), value))
        elif kind.startswith("Int"):
            fields.append("%s=%di" % (key(column), value))
        elif kind.startswith("Float"):
            if value == value and abs(value) != float("inf"):
                fields.append("%s=%r" % (key(column), float(value)))
        else:
            fields.append("%s=\"%s\"" % (key(column), string(str(value))))
    if fields:
        print("%s%s %s %d" % (measurement(table), series, ",".join(fields), stamp))
' "$@"
}

restore_merged() {
  local unit="${1}" scratch="${2}" table day next types columns url token chunks code chunk header rows bytes
  table="${unit%/*}"
  day="${unit##*/}"
  next="$(date -u -d "${day} + 1 day" +%F)"
  types="$(docker exec "${scratch}" influxdb3 query --format json --database "${INFLUXDB3_RESTORE_DATABASE}" \
    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '${table}' AND table_schema = 'iox'" |
    jq -c 'map({(.column_name): .data_type}) | add')" || return 1
  columns="$(jq -r 'keys[] | select(. != "time") | "\"" + . + "\""' <<<"${types}" | paste -sd, -)"
  url="${INFLUXDB3_RESTORE_LIVE_URL:-http://127.0.0.1:${INFLUXDB3_API_PORT:?}}"
  token="${INFLUXDB3_RESTORE_WRITE_TOKEN-${INFLUXDB3_TOKEN_ADMIN:-}}"
  chunks="$(mktemp -d "$(dirname "$(restore_scratch_dir)")/merge.XXXXXX")" || return 1
  docker exec "${scratch}" influxdb3 query --format jsonl --database "${INFLUXDB3_RESTORE_DATABASE}" \
    "SELECT CAST(time AS BIGINT) AS time_ns, ${columns} FROM \"${table}\" WHERE time >= '${day}T00:00:00Z' AND time < '${next}T00:00:00Z'" |
    influxdb3_restore_lp "${table}" "${types}" | influxdb3_restore_niced split -C "${INFLUXDB3_RESTORE_CHUNK_BYTES}" - "${chunks}/chunk." || { rm -rf "${chunks}"; return 1; }
  read -r rows bytes < <(cat "${chunks}"/chunk.* 2>/dev/null | wc -lc)
  header=""
  if [ -n "${token}" ]; then
    header="${chunks}/header"
    (umask 077 && printf 'Authorization: Bearer %s\n' "${token}" >"${header}")
  fi
  for chunk in "${chunks}"/chunk.*; do
    [ -e "${chunk}" ] || continue
    code="$(influxdb3_restore_niced curl -sS -o /dev/null -w '%{http_code}' -X POST "${url}/api/v3/write_lp?db=${INFLUXDB3_RESTORE_DATABASE}&precision=nanosecond" \
      ${header:+--header "@${header}"} --data-binary "@${chunk}")"
    [ "${code}" = "204" ] || { restore_fault "writing [${unit}] to [${url}] returned [${code}]"; rm -rf "${chunks}"; return 1; }
    [ "${INFLUXDB3_RESTORE_WRITE_PAUSE}" = "0" ] || sleep "${INFLUXDB3_RESTORE_WRITE_PAUSE}"
  done
  [ -z "${RESTORE_STATS_FILE:-}" ] || echo "${rows:-0} ${bytes:-0}" >>"${RESTORE_STATS_FILE}"
  rm -rf "${chunks}"
}
