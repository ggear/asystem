#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC2034,SC2153
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${ROOT_DIR}" || exit

chmod +x "./pushcerts.sh"
chmod +x "./pushcerts-hosts.sh"
cp -rvfp "./pushcerts.service" /etc/systemd/system
systemctl daemon-reload
systemctl enable pushcerts.service
systemctl restart pushcerts.service
