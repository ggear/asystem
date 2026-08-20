#!/bin/bash

set -Eeuo pipefail

IFS=$'\n\t'

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
HOSTS_FILE="${ROOT_DIR}/../../../.hosts"
SERVICE_NAME="$(basename "${ROOT_DIR}")"
INSTALL_DIR="/var/lib/asystem/install"
LINE="----------------------------------------------------------------------------------------------------"
FAILED=0

hosts() {
  local label rest machine form
  while IFS='=' read -r label rest; do
    [[ -z "${label}" || "${label}" == \#* ]] && continue
    IFS=',' read -r machine _ _ _ form _ <<<"${rest}"
    case "${form}" in
    edge | server) echo "${machine}-${label}" ;;
    esac
  done <"${HOSTS_FILE}"
}

INSTALL="${INSTALL_DIR}/${SERVICE_NAME}/latest/install.sh"

for HOST in $(hosts); do
  echo ""
  echo "${LINE}"
  echo "Restarting service [${SERVICE_NAME}] on host [${HOST}] ... "
  echo "${LINE}"
  if ! ssh -q "root@${HOST}.local" "[ -f '${INSTALL}' ] && chmod +x '${INSTALL}' && '${INSTALL}' start"; then
    FAILED=$((FAILED + 1))
    echo "WARN: Restart failed on host [${HOST}], missing or failed [${INSTALL}]" >&2
  fi
done

echo ""
if [[ "${FAILED}" -gt 0 ]]; then
  echo "ERROR: Restart failed on [${FAILED}] hosts" >&2
  exit 1
fi
echo "Restarted service [${SERVICE_NAME}] on every host"
