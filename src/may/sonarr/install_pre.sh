#!/bin/bash

. ./.env

SONARR_SHARE_ROOT_DIR="/share/$(echo "${SONARR_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SONARR_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SONARR_SHARE_ROOT_DIR}"; then
  touch "${SONARR_SHARE_DIR}/.sonarr"
else
  echo "Error: [${SONARR_SHARE_ROOT_DIR}] missing or not mounted"
fi
