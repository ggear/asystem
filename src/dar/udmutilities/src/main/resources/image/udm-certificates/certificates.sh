#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <mode> <host-pull> <host-push>"
  exit 1
fi
if [ "$1" = "pull" ]; then
  echo "Pulling certificates ..."
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/privkey.pem" "$ROOT_DIR/.key.pem" || exit 1
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/fullchain.pem" "$ROOT_DIR/certificate.pem" || exit 1
  echo "$2:/home/asystem/letsencrypt/latest/certificates -> localhost:$ROOT_DIR"
  echo "Pulling certificates ... done"
elif [ "$1" = "push" ]; then
  echo "Pushing certificates ..."
  for DIR in "/home/asystem/udmutilities/latest" "/var/lib/asystem/install/udmutilities/latest/data"; do
    ssh -n -q -o "StrictHostKeyChecking=no" "root@$3" "[ -d $DIR ]" || continue
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/.key.pem" "root@$3:$DIR" || exit 1
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/certificate.pem" "root@$3:$DIR" || exit 1
    echo "localhost:$ROOT_DIR -> $3:$DIR"
  done
  echo "Restarting service on [$3] ... "
  ssh -q -o "StrictHostKeyChecking=no" "root@$3" "/var/lib/asystem/install/udmutilities/latest/install.sh" || exit 1
  echo "Pushing certificates ... done"
fi
exit 0