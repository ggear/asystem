#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

SABNZBD_SHARE_ROOT_DIR="/share/$(echo "${SABNZBD_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SABNZBD_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SABNZBD_SHARE_ROOT_DIR}"; then
  chown graham:users "${SABNZBD_SHARE_DIR}"
  chmod g+rwXs "${SABNZBD_SHARE_DIR}"
else
  echo "Error [${SABNZBD_SHARE_ROOT_DIR}] missing or not mounted"
fi
