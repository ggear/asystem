#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <mode> <host-pull> <host-push>"
  exit 1
fi
if [ "$1" = "pull" ]; then
  scp -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" -pr "root@$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/privkey.pem" "$ROOT_DIR/.key.pem"
  scp -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" -pr "root@$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/fullchain.pem" "$ROOT_DIR/certificate.pem"
  echo "$2:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com -> localhost:$ROOT_DIR"
elif [ "$1" = "push" ]; then
  for DIR in "/home/asystem/nginx/latest/" "/var/lib/asystem/install/nginx/latest/config/"; do
    scp -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" -pr "$ROOT_DIR/.key.pem" "root@$3:$DIR"
    scp -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" -pr "$ROOT_DIR/certificate.pem" "root@$3:$DIR"
    echo "localhost:$ROOT_DIR -> $3:$DIR"
  done
  echo "Certificates pushed, restarting service on [$3] ... "
  ssh -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" "root@$3" "/var/lib/asystem/install/nginx/latest/install.sh"
fi
exit 0