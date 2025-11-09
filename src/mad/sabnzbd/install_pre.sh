#!/bin/bash

. ./.env

# TODO: Check share mounted, if not attempt mount. if not failed, write a place holder, check placeholder in health
SABNZBD_SHARE_ROOT_DIR="/share/$(echo "${SABNZBD_SHARE_DIR}" | awk -F'/' '{print $3}')"
if grep -qE '^[^#].*[[:space:]]+'"${SABNZBD_SHARE_ROOT_DIR}"'[[:space:]]' /etc/fstab && mountpoint -q "${SABNZBD_SHARE_ROOT_DIR}"; then
  echo "${SABNZBD_SHARE_ROOT_DIR} is configured and mounted"
else
  echo "${SABNZBD_SHARE_ROOT_DIR} missing or not mounted"
fi





for DIR in "enqueued" "finished" "reencoding" "staging"; do
  mkdir -p "${SABNZBD_SHARE_DIR}/$DIR"
done
chown -R graham:users "${SABNZBD_SHARE_DIR}"
mkdir -p /home/asystem/sabnzbd/latest/scripts
cp -rvf /var/lib/asystem/install/media/latest/bin/lib/ingress.py /home/asystem/sabnzbd/latest/scripts
chmod +x /home/asystem/sabnzbd/latest/scripts/*.sh
