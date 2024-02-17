#!/bin/sh

. ./.env

for DIR in "enqueued" "finished" "reencoding" "staging"; do
  mkdir -p "${SABNZBD_SHARE_DIR}/$DIR"
done
chown -R graham:users "${SABNZBD_SHARE_DIR}"
