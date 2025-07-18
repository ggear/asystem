#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <mode> <host-pull> <host-push>"
  exit 1
fi
if [ "$1" = "pull" ]; then
  echo "Pulling certificates ..."
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/privkey.pem" "$ROOT_DIR/.key.pem"
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/fullchain.pem" "$ROOT_DIR/certificate.pem"
  echo "$2:/home/asystem/letsencrypt/latest/certificates -> localhost:$ROOT_DIR"
  echo "Pulling certificates ... done"
elif [ "$1" = "push" ]; then
  echo "Pushing certificates ..."
  for DIR in "/home/asystem/appdaemon/latest" "/var/lib/asystem/install/appdaemon/latest/data"; do
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/.key.pem" "root@$3:$DIR"
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/certificate.pem" "root@$3:$DIR"
    echo "localhost:$ROOT_DIR -> $3:$DIR"
  done
  echo "Restarting service on [$3] ... "
  ssh -q -o "StrictHostKeyChecking=no" "root@$3" "/var/lib/asystem/install/appdaemon/latest/install.sh"
  echo "Pushing certificates ... done"
fi
exit 0