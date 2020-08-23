#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cp -rvfp "${SERVICE_INSTALL}/pushcerts.service" /etc/systemd/system
systemctl daemon-reload
systemctl enable pushcerts.service
systemctl restart pushcerts.service
