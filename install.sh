#!/usr/bin/env bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

# shellcheck disable=SC2153

set -Eeuo pipefail

IFS=$'\n\t'

log_info() { echo "$*"; }
log_warn() { echo "WARN: $*" >&2; }
log_error() { echo "ERROR: $*" >&2 && exit 1; }

run_hook() {
  local hook_path="$1"
  if [[ -f "${hook_path}" ]]; then
    chmod +x "${hook_path}"
    "${hook_path}" || log_warn "Hook failed but continuing: ${hook_path}"
  fi
}

run_backup() {
  local backup_script="${SERVICE_INSTALL}/backup.sh" backup_source
  [[ -f "${backup_script}" ]] || return 0
  if [[ "${COMMAND}" != "install" ]]; then
    log_info "Backup skipped, command is [${COMMAND}] not [install]"
    return 0
  fi
  if ! docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE_NAME}"; then
    log_warn "Backup skipped, container is not running [${SERVICE_NAME}]"
    return 0
  fi
  backup_source="$(readlink -f "${SERVICE_PARENT}/latest")"
  if [[ ! -d "${backup_source}" ]]; then
    log_warn "Backup skipped, no current home [${SERVICE_PARENT}/latest]"
    return 0
  fi
  if [[ "${backup_source}" == "${SERVICE_HOME}" ]]; then
    log_info "Backup skipped, reinstalling the current version [${SERVICE_VERSION_ABSOLUTE}]"
    return 0
  fi
  chmod +x "${backup_script}"
  BACKUP_SOURCE_PATH="${backup_source}" BACKUP_SKIP_HOURS=0 BACKUP_SERVICE_RESTART=false \
    timeout 1800 "${backup_script}" || {
    docker start "${SERVICE_NAME}" >/dev/null 2>&1 || true
    log_error "Backup failed, abandoning the install of [${SERVICE_VERSION_ABSOLUTE}] and restoring [${backup_source}] [${backup_script}]"
  }
}

SERVICE_WAIT_EXECUTING_SECONDS=300
SERVICE_WAIT_HEALTHY_SECONDS=900
SERVICE_WAIT_RESTART_SECONDS=120
SERVICE_SETTLE_RESTART_SECONDS=30

wait_service() {
  local script="$1" label="$2" interval="$3" timeout="$4" fatal="$5" waited=0 grace=5 report=5
  ((interval > 0)) || interval=1
  echo "Waiting for service to ${label} ..."
  while ! docker exec "${SERVICE_NAME}" "/asystem/etc/${script}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      echo "Waiting for service to ${label} ... failed after [${waited}] of [${timeout}] seconds"
      docker exec "${SERVICE_NAME}" "/asystem/etc/${script}" -v 2>&1 | tail -n 5
      if [[ "${fatal}" == "true" ]]; then
        log_error "Service failed to ${label} within [${timeout}] seconds [${SERVICE_NAME}]"
      fi
      log_warn "Service failed to ${label} within [${timeout}] seconds [${SERVICE_NAME}]"
      return 1
    fi
    if ((waited == grace)) || ((waited > 0 && waited % report == 0)); then
      echo "Waiting for service to ${label} ... waited [${waited}] of [${timeout}] seconds"
      docker exec "${SERVICE_NAME}" "/asystem/etc/${script}" -v 2>&1 | tail -n 3
    fi
    sleep "${interval}"
    waited=$((waited + interval))
  done
  echo "Waiting for service to ${label} ... done after [${waited}] of [${timeout}] seconds"
}

retire_home() {
  local home="${1:-}" reason=""
  if [[ -z "${home}" ]]; then
    reason="empty path"
  elif [[ -L "${home}" ]]; then
    reason="symlink"
  elif [[ ! -d "${home}" ]]; then
    reason="not a directory"
  elif [[ "$(dirname "${home}")" != "${SERVICE_PARENT}" ]]; then
    reason="outside [${SERVICE_PARENT}]"
  elif [[ ! "$(basename "${home}")" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9]+)?$ ]]; then
    reason="not a version"
  elif [[ "${home}" == "${SERVICE_HOME}" ]]; then
    reason="current home"
  elif [[ "${home}" == "${SERVICE_HOME_OLD}" ]]; then
    reason="source home"
  fi
  if [[ -n "${reason}" ]]; then
    log_warn "Retire skipped, ${reason} [${home}]"
    return 0
  fi
  log_info "Retiring old home [${home}]"
  rm -rf "${home}"
}

stop_service() {
  local container
  for container in "${SERVICE_NAME}" "${SERVICE_NAME}_bootstrap"; do
    docker stop "${container}" >/dev/null 2>&1 || true
    docker wait "${container}" >/dev/null 2>&1 || true
    docker rm -f "${container}" >/dev/null 2>&1 || true
  done
}

start_service() {
  docker compose --compatibility --ansi never up --force-recreate -d
}

restart_service() {
  if ! docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE_NAME}"; then
    log_warn "Restart skipped, container is not running [${SERVICE_NAME}]"
    return 0
  fi
  log_info "Restarting service to republish its retained topics [${SERVICE_NAME}]"
  if ! docker restart "${SERVICE_NAME}" >/dev/null 2>&1; then
    log_warn "Restart failed [${SERVICE_NAME}]"
    return 0
  fi
  if [[ -f "image/checkexecuting.sh" ]]; then
    wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_RESTART_SECONDS}" false || true
  else
    sleep "${SERVICE_SETTLE_RESTART_SECONDS}"
  fi
}

COMMAND="start"
[[ "$#" -ge 1 ]] && COMMAND="$1"
case "${COMMAND}" in
install | start | stop | sleep | schema) ;;
*) log_error "Unknown command [${COMMAND}] expected [install] [start] [stop] [sleep] or [schema]" ;;
esac
SCHEMA_ROLE="all"
[[ "${COMMAND}" == "schema" && "$#" -ge 2 ]] && SCHEMA_ROLE="$2"
case "${SCHEMA_ROLE}" in
all | broker | database) ;;
*) log_error "Unknown schema role [${SCHEMA_ROLE}] expected [broker] [database] or none" ;;
esac

export SERVICE_COMMAND="${COMMAND}"
export SERVICE_VERSION_CHANGED="false"

SERVICE_INSTALL="/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"
SERVICE_SLEEP="/var/lib/asystem/install/${SERVICE_NAME}/.sleep"
[[ -d "${SERVICE_INSTALL}" ]] || log_error "Install directory does not exist: ${SERVICE_INSTALL}"
cd "${SERVICE_INSTALL}"

if [[ -f "${SERVICE_INSTALL}/.sleep" ]]; then
  mv -f "${SERVICE_INSTALL}/.sleep" "${SERVICE_SLEEP}"
fi

if [[ "${COMMAND}" == "stop" || "${COMMAND}" == "sleep" ]]; then
  stop_service
  if [[ "${COMMAND}" == "sleep" ]]; then
    touch "${SERVICE_SLEEP}"
    log_info "Service put to sleep"
  else
    rm -f "${SERVICE_SLEEP}"
    log_info "Service stopped"
  fi
  exit 0
fi

run_hook "./install_prep.sh"
cd "${SERVICE_INSTALL}"
touch .env
chmod 600 .env
# shellcheck disable=SC1091
source .env

if [[ "${COMMAND}" == "schema" ]]; then
  if [[ "${SCHEMA_ROLE}" != "broker" && -x "image/database.sh" ]]; then
    ./image/database.sh
  fi
  if [[ "${SCHEMA_ROLE}" != "database" && -x "image/broker.sh" ]]; then
    restart_service
    ./image/broker.sh publish
  fi
  exit 0
fi

rm -f "${SERVICE_SLEEP}"

if [[ "${SERVICE_FORM_FACTOR:-}" == "edge" || "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  SERVICE_HOME="/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"
  SERVICE_PARENT="$(dirname "${SERVICE_HOME}")"
  if [[ "$(readlink -f "${SERVICE_PARENT}/latest" 2>/dev/null || true)" != "${SERVICE_HOME}" ]]; then
    export SERVICE_VERSION_CHANGED="true"
  fi
  mapfile -t EXISTING_HOMES < <(find "${SERVICE_PARENT}" -maxdepth 1 -mindepth 1 -type d ! -name latest 2>/dev/null |
    grep -E '/[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9]+)?$' | sort)
  SERVICE_HOME_OLD=""
  SERVICE_HOME_OLDEST=()
  if ((${#EXISTING_HOMES[@]} > 0)); then
    LAST_HOME_INDEX=$((${#EXISTING_HOMES[@]} - 1))
    SERVICE_HOME_OLD="${EXISTING_HOMES[${LAST_HOME_INDEX}]}"
    if ((${#EXISTING_HOMES[@]} > 1)); then
      SERVICE_HOME_OLDEST=("${EXISTING_HOMES[@]:0:${#EXISTING_HOMES[@]}-1}")
    fi
  fi
  IMAGE_TAR="${SERVICE_NAME}-${SERVICE_VERSION_ABSOLUTE}.tar.gz"
  [[ -f "${IMAGE_TAR}" ]] && docker image load -i "${IMAGE_TAR}"
  if [[ -f "docker-compose.yml" ]]; then
    run_backup
    stop_service
    docker system prune --volumes -f >/dev/null 2>&1 || true
  fi
  if [[ ! -d "${SERVICE_HOME}" ]]; then
    mkdir -p "${SERVICE_HOME}"
    chmod 777 "${SERVICE_HOME}"
    if [[ "$(stat -f -c %T "${SERVICE_HOME}" 2>/dev/null || true)" == "btrfs" ]]; then
      chattr +C "${SERVICE_HOME}" || true
    fi
    if [[ -n "${SERVICE_HOME_OLD}" && -d "${SERVICE_HOME_OLD}" ]]; then
      REQUIRED_KB="$(du -sk "${SERVICE_HOME_OLD}" | cut -f1)"
      AVAILABLE_KB="$(df -Pk "${SERVICE_PARENT}" | awk 'NR==2 {print $4}')"
      if ((AVAILABLE_KB < REQUIRED_KB)); then
        log_error "Insufficient space to copy home, need [$((REQUIRED_KB / 1024))] MB have [$((AVAILABLE_KB / 1024))] MB [${SERVICE_HOME_OLD}]"
      fi
      log_info "Copying old home [$((REQUIRED_KB / 1024))] MB to new ..."
      cp -rfpa "${SERVICE_HOME_OLD}/." "${SERVICE_HOME}"
    fi
    if [[ "${COMMAND}" == "install" ]] && ((${#SERVICE_HOME_OLDEST[@]} > 0)); then
      for HOME_OLDEST in "${SERVICE_HOME_OLDEST[@]}"; do
        retire_home "${HOME_OLDEST}"
      done
    fi
  fi
  shopt -s dotglob nullglob
  DATA_ENTRIES=(data/*)
  if ((${#DATA_ENTRIES[@]} > 0)); then
    cp -rfpv "${DATA_ENTRIES[@]}" "${SERVICE_HOME}"
  fi
  shopt -u dotglob nullglob
  rm -f "${SERVICE_PARENT}/latest"
  ln -sfv "${SERVICE_HOME}" "${SERVICE_PARENT}/latest"
  run_hook "./install_pre.sh"
  if [[ -f "docker-compose.yml" ]]; then
    start_service
    if docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE_NAME}_bootstrap"; then
      sleep 1
      docker logs "${SERVICE_NAME}_bootstrap" -f
    fi
    echo "--------------------------------------------------------------------------------"
    docker ps -f name="${SERVICE_NAME}"
    echo "--------------------------------------------------------------------------------"
    if find "${SERVICE_INSTALL}" -name checkexecuting.sh | grep -q . && find "${SERVICE_INSTALL}" -name checkhealthy.sh | grep -q .; then
      echo
      wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_EXECUTING_SECONDS}" true
      echo
      wait_service "checkhealthy.sh" "become healthy" 5 "${SERVICE_WAIT_HEALTHY_SECONDS}" true
      echo
      docker exec -i "${SERVICE_NAME}" bash -c 'command -v stdbuf >/dev/null 2>&1 && exec stdbuf -oL /asystem/etc/checkhealthy.sh -v || exec /asystem/etc/checkhealthy.sh -v'
      echo && echo
      sleep 1
    else
      log_error "Service does not have health scripts defined"
    fi
    echo "--------------------------------------------------------------------------------"
    docker ps -f name="${SERVICE_NAME}"
    echo "--------------------------------------------------------------------------------"
    docker logs "${SERVICE_NAME}"
    echo "--------------------------------------------------------------------------------"
    if ! docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE_NAME}"; then
      log_error "Service failed to start"
    else
      docker system prune --volumes -f -a >/dev/null 2>&1 || true
      echo "Service started successfully"
      echo "--------------------------------------------------------------------------------"
    fi
  fi
fi
run_hook "./install_post.sh"
