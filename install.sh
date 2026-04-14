#!/usr/bin/env bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

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

SERVICE_INSTALL="/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"
[[ -d "${SERVICE_INSTALL}" ]] || log_error "Install directory does not exist: ${SERVICE_INSTALL}"
cd "${SERVICE_INSTALL}"
run_hook "./install_prep.sh"
cd "${SERVICE_INSTALL}"
touch .env
chmod 600 .env
source .env
if [[ "${SERVICE_FORM_FACTOR:-}" == "edge" || "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  SERVICE_HOME="/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"
  SERVICE_PARENT="$(dirname "${SERVICE_HOME}")"
  mapfile -t EXISTING_HOMES < <(find "${SERVICE_PARENT}" -maxdepth 1 -mindepth 1 -type d ! -name latest 2>/dev/null | sort)
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
    docker stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
    docker stop "${SERVICE_NAME}_bootstrap" >/dev/null 2>&1 || true
    docker wait "${SERVICE_NAME}" >/dev/null 2>&1 || true
    docker wait "${SERVICE_NAME}_bootstrap" >/dev/null 2>&1 || true
    docker system prune --volumes -f >/dev/null 2>&1 || true
  fi
  if [[ ! -d "${SERVICE_HOME}" ]]; then
    mkdir -p "${SERVICE_HOME}"
    chmod 777 "${SERVICE_HOME}"
    if [[ "$(stat -f -c %T "${SERVICE_HOME}" 2>/dev/null || true)" == "btrfs" ]]; then
      chattr +C "${SERVICE_HOME}" || true
    fi
    if [[ -n "${SERVICE_HOME_OLD}" && -d "${SERVICE_HOME_OLD}" ]]; then
      log_info "Copying old home to new ..."
      cp -rfpa "${SERVICE_HOME_OLD}/." "${SERVICE_HOME}"
    fi
    if ((${#SERVICE_HOME_OLDEST[@]} > 0)); then
      rm -rf "${SERVICE_HOME_OLDEST[@]}"
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
    docker compose --compatibility --ansi never up --force-recreate -d
    if docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE_NAME}_bootstrap"; then
      sleep 1
      docker logs "${SERVICE_NAME}_bootstrap" -f
    fi
    echo "--------------------------------------------------------------------------------"
    docker ps -f name="${SERVICE_NAME}"
    echo "--------------------------------------------------------------------------------"
    if find "${SERVICE_INSTALL}" -name checkexecuting.sh | grep -q . && find "${SERVICE_INSTALL}" -name checkhealthy.sh | grep -q .; then
      echo
      while ! docker exec "${SERVICE_NAME}" /asystem/etc/checkexecuting.sh; do
        echo "Waiting for service to start executing ..."
        sleep 1
      done
      echo && echo "Waiting to check service health ... " && echo && sleep 2
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
