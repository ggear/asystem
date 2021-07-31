#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

key_copy() {
  if [ -d "${3}" ]; then
    mkdir -p ${3}/${1}/.ssh
    chown ${1} ${3}/${1}/.ssh
    cp -rvf ./config/id_rsa.pub ${3}/${1}/.ssh
    chown ${1} ${3}/${1}/.ssh/id_rsa.pub
    cp -rvf ./config/.id_rsa ${3}/${1}/.ssh/id_rsa
    chown ${1} ${3}/${1}/.ssh/id_rsa

    rm -rvf ${3}/${1}/id_rsa*

  fi
}

key_copy 'root' 'root' ''
key_copy 'graham' 'users' '/home'
key_copy 'graham' 'staff' '/Users'

rm -rfv ./config/.id_rsa
