#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
chmod +x "./pushcerts.sh"
cp -rvfp "./pushcerts.service" /etc/systemd/system
systemctl daemon-reload
systemctl enable pushcerts.service
systemctl restart pushcerts.service
