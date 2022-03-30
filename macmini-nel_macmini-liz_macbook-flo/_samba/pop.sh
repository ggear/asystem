#!/bin/sh

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

for HOST in ${HOSTS}; do
  echo "------------------------------------------------------------" && echo "IMPORT MEDIA: ${HOST}" && echo ""
  ssh -o StrictHostKeyChecking=no root@${HOST} "\$(find /root/install/macmini-nel_macmini-liz_macbook-flo/_samba -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1)/config/import.sh"
  echo "------------------------------------------------------------"
done
