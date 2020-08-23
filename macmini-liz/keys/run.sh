#!/bin/sh

set -x

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit
cp -rvf ./config/id_rsa.pub /root/.ssh
cp -rvf ./config/.id_rsa /root/.ssh/id_rsa
rm -rfv ./config/.id_rsa
