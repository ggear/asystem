# shellcheck shell=bash

stage_start() {
  local service script running health failed=0 count=0
  for service in $(jq -r --arg h "${BACKUP_HOST}" \
    '.asystem.schema[] | select(.host == $h) | .services[]' "${BACKUP_CONFIG}" 2>/dev/null); do
    script="${BACKUP_INSTALL_ROOT}/${service}/latest/backup.sh"
    [ -x "${script}" ] || continue
    running="$(docker ps --filter "name=^/${service}$" --filter "status=running" --format '{{.Names}}')"
    if [ "${running}" != "${service}" ]; then
      echo "[primary] skipping [${service}], container is not running"
      continue
    fi
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${service}" 2>/dev/null)"
    if [ "${health}" = "starting" ]; then
      echo "[primary] skipping [${service}], container is still starting"
      continue
    fi
    count=$(( count + 1 ))
    local dir="${BACKUP_STAGE_DIR}/service/${service}"
    mkdir -p "${dir}"
    local started; started="$(date +%s)"
    echo "[primary] backing up [${service}]"
    local rc=0
    BACKUP_SKIP_HOURS="${BACKUP_SKIP_HOURS:-1}" BACKUP_SERVICE_RESTART=true BACKUP_TIMEOUT_HOURS="${BACKUP_TIMEOUT_HOURS}" \
      bash "${script}" >"${dir}/output.log" 2>&1 || rc=$?
    local state=complete ok=true
    [ "${rc}" -eq 0 ] || { state=failed; ok=false; failed=$(( failed + 1 )); }
    local newest size=0 files=0 kind=unknown
    newest="$(find "${BACKUP_HOME_ROOT}/${service}/backup" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | tail -1)"
    if [ -n "${newest}" ]; then
      size="$(du -m -s "${newest}" 2>/dev/null | cut -f1)"
      size="${size:-0}"
      files="$(find "${newest}" -type f 2>/dev/null | wc -l | tr -d ' ')"
      case "$(basename "${newest}")" in *_delta) kind="delta" ;; *_full) kind="full" ;; esac
    fi
    cat >"${dir}/status.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "backup_id": "$(basename "${newest:-none}")",
  "state": "${state}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "success_bool": ${ok},
  "kind": "${kind}",
  "version": "$(basename "$(readlink -f "${BACKUP_HOME_ROOT}/${service}/latest" 2>/dev/null || echo unknown)")",
  "file_count": ${files:-0},
  "size_mb": ${size:-0}
}
JSON
    mv "${dir}/status.json.tmp" "${dir}/status.json"
    BACKUP_FILES=$(( BACKUP_FILES + files ))
    BACKUP_SIZE=$(( BACKUP_SIZE + size ))
    [ "${rc}" -eq 0 ] && BACKUP_FILES_CREATED=$(( BACKUP_FILES_CREATED + 1 ))
    backup_publish "supervisor/${BACKUP_HOST}/backup/stage/primary/service/${service}/status" "$(cat "${dir}/status.json")"
  done
  echo "[primary] attempted [${count}] services, [${failed}] failed"
  backup_usage "${BACKUP_HOME_ROOT}"
  return "${failed}"
}

stage_stop() {
  pkill -TERM -f "${BACKUP_INSTALL_ROOT}/[a-z0-9_-]*/latest/backup.sh" 2>/dev/null || true
}
