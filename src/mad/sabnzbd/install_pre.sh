#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091 # .env is generated at build time, not available to shellcheck
. "${ROOT_DIR}/.env"

SABNZBD_SHARE_ROOT_DIR="/share/$(echo "${SABNZBD_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SABNZBD_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SABNZBD_SHARE_ROOT_DIR}"; then
  for DIR in "enqueued" "finished" "reencoding" "staging"; do
    mkdir -p "${SABNZBD_SHARE_DIR}/$DIR"
  done
  chown -R graham:users "${SABNZBD_SHARE_DIR}"
  chmod -R g+rwX "${SABNZBD_SHARE_DIR}"
  find "${SABNZBD_SHARE_DIR}" -type d -exec chmod g+s {} +
  touch "${SABNZBD_SHARE_DIR}/.sabnzbd"
else
  echo "Error: [${SABNZBD_SHARE_ROOT_DIR}] missing or not mounted"
fi
mkdir -p /home/asystem/sabnzbd/latest/scripts
cp -rvf /var/lib/asystem/install/media/latest/bin/lib/ingress.py /home/asystem/sabnzbd/latest/scripts
chmod +x /home/asystem/sabnzbd/latest/scripts/*.sh
