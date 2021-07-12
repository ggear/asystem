#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

USER=root
GROUP=root
HOME=/root
if [ -d /Users/graham ]; then
  USER=graham
  GROUP=staff
  HOME=/Users/graham
fi

cp -rvf ./config/id_rsa.pub ${HOME}/.ssh
cp -rvf ./config/.id_rsa ${HOME}/.ssh/id_rsa
rm -rfv ./config/.id_rsa
