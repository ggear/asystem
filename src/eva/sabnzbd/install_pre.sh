#!/bin/sh

. .env

for DIR in "enqueued" "finished" "staging"; do
  mkdir -p "${SABNZBD_SHARE_DIR}/$DIR"
  chown -R graham:users "${SABNZBD_DOWNLOAD_DIR}/$DIR"
done
