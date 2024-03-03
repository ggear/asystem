#!/bin/sh

. ./.env

for DIR in "enqueued" "finished" "reencoding" "staging"; do
  mkdir -p "${SABNZBD_SHARE_DIR}/$DIR"
done
chown -R graham:users "${SABNZBD_SHARE_DIR}"
mkdir -p /home/asystem/sabnzbd/latest/scripts
cp -rvf /var/lib/asystem/install/media/latest/config/all.sh /home/asystem/sabnzbd/latest/scripts
chmod +x /home/asystem/sabnzbd/latest/scripts/*.sh
