#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

# INFO: Disable push certs in favour of manual deploy
#chmod +x "./pushcerts.sh"
#chmod +x "./pushcerts_copy.sh"
#cp -rvfp "./pushcerts.service" /etc/systemd/system
#systemctl daemon-reload
#systemctl enable pushcerts.service
#systemctl restart pushcerts.service
