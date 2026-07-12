#!/bin/bash

. ./.env

SONARR_SHARE_ROOT_DIR="/share/$(echo "${SONARR_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SONARR_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SONARR_SHARE_ROOT_DIR}"; then
  touch "${SONARR_SHARE_DIR}/.sonarr"
else
  echo "Error: [${SONARR_SHARE_ROOT_DIR}] missing or not mounted"
fi

SABNZBD_SHARE_ROOT_DIR="/share/$(echo "${SABNZBD_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SABNZBD_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SABNZBD_SHARE_ROOT_DIR}"; then
  touch "${SABNZBD_SHARE_DIR}/.sonarr"
else
  echo "Error: [${SABNZBD_SHARE_ROOT_DIR}] missing or not mounted"
fi
