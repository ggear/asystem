#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
SHARES_FILE="${ROOT_DIR}/src/main/resources/shares.csv"

[ -f "${SHARES_FILE}" ] || {
  echo "Missing shares file [${SHARES_FILE}]" >&2
  exit 1
}

HOSTS="$(cut -d "," -f 1 "${SHARES_FILE}" | sort -u)"
HOST="$(echo "${HOSTS}" | head -1)"

echo "------------------------------------------------------------" && echo "Executing remotely ..."
ssh -o StrictHostKeyChecking=no "root@${HOST}" "/root/install/media/latest/bin/media-truncate.sh"
ssh -o StrictHostKeyChecking=no "root@${HOST}" "/root/install/media/latest/bin/media-refresh.sh"
echo "------------------------------------------------------------"

for HOST in ${HOSTS}; do
  echo "------------------------------------------------------------" && echo "Executing remotely ..."
  ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "/root/install/media/latest/bin/media-normalise.sh"
  ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "/root/install/media/latest/bin/media-clean.sh"
  ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "/root/install/media/latest/bin/media-analyse.sh"
  ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "/root/install/media/latest/bin/media-space.sh"
  echo "------------------------------------------------------------"
done
