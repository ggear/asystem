#!/bin/bash

nohup rsync -rltDv --no-perms --no-owner --no-group --progress \
  --include="*/" \
  --include="*.mkv" \
  --exclude="*" \
  "/share/41/media/parents/series/The Wire/" \
  "/media/usbdrive/Shows/The Wire/" \
  >/tmp/rsync_thewire.log 2>&1 &
disown
