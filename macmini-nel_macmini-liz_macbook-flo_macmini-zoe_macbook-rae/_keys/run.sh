#!/bin/sh

SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

key_copy() {
  if [ -d "${3}${1}" ]; then
    mkdir -p ${3}${1}/.ssh
    cp -rvf ./config/id_rsa.pub ${3}${1}/.ssh
    cp -rvf ./config/.id_rsa ${3}${1}/.ssh/id_rsa
    chown -R ${1} ${3}${1} 2>/dev/null || true
    chgrp -R ${2} ${3}${1} 2>/dev/null || true
  fi
}

key_copy 'root' 'root' '/'
key_copy 'root' 'root' '/var/'
key_copy 'graham' 'users' '/home/'
key_copy 'graham' 'staff' '/Users/'
