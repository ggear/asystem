#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

if [ -z "$1" ] || [ "$1" = "pull" ]; then
  scp -qpr "root@$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/privkey.pem" "$ROOT_DIR/.key.pem"
  scp -qpr "root@$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/fullchain.pem" "$ROOT_DIR/certificate.pem"
  echo "$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com -> localhost:$ROOT_DIR"
elif [ "$1" = "push" ]; then
  for DIR in "/home/asystem/udmutilities/latest/udm-certificates/" "/var/lib/asystem/install/udmutilities/latest/config/udm-certificates/"; do
    scp -qpr "$ROOT_DIR/.key.pem" "root@$3:$DIR"
    scp -qpr "$ROOT_DIR/certificate.pem" "root@$3:$DIR"
    echo "localhost:$ROOT_DIR -> $3:$DIR"
  done
  echo "Certificates pushed, restarting service on [$3] ... "
  ssh "root@$3" "/var/lib/asystem/install/udmutilities/latest/install.sh"
fi