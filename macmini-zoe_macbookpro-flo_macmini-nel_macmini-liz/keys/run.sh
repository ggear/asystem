#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
cp -rvf ./config/id_rsa.pub /root/.ssh
cp -rvf ./config/.id_rsa /root/.ssh/id_rsa
rm -rfv ./config/.id_rsa
