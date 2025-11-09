#!/bin/bash

. ./.env

if [ "$(find /share -mindepth 1 -maxdepth 1 -type d | wc -l)" -ne "$(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l)" ]; then
  systemctl stop smb nmb
  for share_dir in $(find /share -mindepth 1 -maxdepth 1 -type d); do
    umount -f $share_dir
    mount $share_dir
  done
  systemctl start smb nmb
fi
[ "$(find /share -mindepth 1 -maxdepth 1 -type d | wc -l)" -ne "$(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l)" ] && echo "Could not mount all shares"
