#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit

#cp -rvf "${SERVICE_INSTALL}/" /etc/systemd/system
systemctl daemon-reload
systemctl enable myservice.service
systemctl start myservice.service

