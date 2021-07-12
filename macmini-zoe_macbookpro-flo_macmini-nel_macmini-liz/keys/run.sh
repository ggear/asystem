#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

USER=root
HOME=/root
if [ -d /Users/graham ]; then
  USER=graham
  HOME=/Users/graham
fi

cp -rvf ./config/id_rsa.pub ${HOME}/.ssh
chown ${USER} ${HOME}/.ssh/id_rsa.pub
cp -rvf ./config/.id_rsa ${HOME}/.ssh/id_rsa
chown ${USER} ${HOME}/.ssh/id_rsa
rm -rfv ./config/.id_rsa
