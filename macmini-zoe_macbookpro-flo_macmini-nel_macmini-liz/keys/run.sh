#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

USER=root
HOME=/root/.ssh
if [ -d /Users/graham ]; then
  USER=graham
  HOME=/Users/graham
fi

mkdir -p ${HOME}
chown ${USER} ${HOME}
cp -rvf ./config/id_rsa.pub ${HOME}
chown ${USER} ${HOME}/id_rsa.pub
cp -rvf ./config/.id_rsa ${HOME}/id_rsa
chown ${USER} ${HOME}/id_rsa
rm -rfv ./config/.id_rsa
