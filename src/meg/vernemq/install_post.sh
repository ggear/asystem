#!/bin/bash

set -Eeuo pipefail

IFS=$'\n\t'

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
HOSTS_FILE="${ROOT_DIR}/hosts"
INSTALL_DIR="/var/lib/asystem/install"
SSH_ARGS=(-q -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
LINE="----------------------------------------------------------------------------------------------------"
FAILED=0
SKIPPED=0
PUBLISHED=0

if [[ ! -f "${HOSTS_FILE}" ]]; then
  echo "WARN: Republish skipped, no host list at [${HOSTS_FILE}]" >&2
  exit 0
fi

while IFS= read -r HOST; do
  [[ -z "${HOST}" ]] && continue
  echo ""
  echo "${LINE}"
  echo "Republishing retained topics on host [${HOST}] ... "
  echo "${LINE}"
  set +e
  ssh "${SSH_ARGS[@]}" "root@${HOST}.local" bash -s "${INSTALL_DIR}" <<'REMOTE'
set -eu
FOUND=0
while IFS= read -r SCRIPT; do
  [ -x "$(dirname "${SCRIPT}")/image/broker.sh" ] || continue
  FOUND=$((FOUND + 1))
  echo "Running [${SCRIPT}]"
  "${SCRIPT}" schema broker
done < <(find -L "$1"/*/latest -maxdepth 1 -name install.sh 2>/dev/null | sort)
echo "Republished [${FOUND}] modules"
REMOTE
  STATUS=$?
  set -e
  if [[ "${STATUS}" -eq 255 ]]; then
    SKIPPED=$((SKIPPED + 1))
    echo "Republish skipped, host unreachable [${HOST}]"
  elif [[ "${STATUS}" -ne 0 ]]; then
    FAILED=$((FAILED + 1))
    echo "WARN: Republish failed with status [${STATUS}] on host [${HOST}]" >&2
  else
    PUBLISHED=$((PUBLISHED + 1))
  fi
done <"${HOSTS_FILE}"

echo ""
echo "Republished [${PUBLISHED}] hosts, skipped [${SKIPPED}] unreachable, failed [${FAILED}]"
if [[ "${FAILED}" -gt 0 ]]; then
  echo "ERROR: Retained topics are missing on [${FAILED}] hosts until this is re-run" >&2
  exit 1
fi
