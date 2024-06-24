#!/bin/bash

INSTALL_DIR="/root/install/media/latest/config"
PYTHON_DIR="/root/.pyenv/versions/${PYTHON_VERSION}/bin"
SHARE_DIRS=$(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}')

${INSTALL_DIR}/import.sh /share/2/tmp
for SHARE_DIR in ${SHARE_DIRS}; do ${INSTALL_DIR}/normalise.sh ${SHARE_DIR}; done
for SHARE_DIR in ${SHARE_DIRS}; do ${PYTHON_DIR}/python ${INSTALL_DIR}/rename.py ${SHARE_DIR}/tmp; done
for SHARE_DIR in ${SHARE_DIRS}; do ${PYTHON_DIR}/python ${INSTALL_DIR}/analyse.py ${SHARE_DIR}/media "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8"; done
${INSTALL_DIR}/library.sh
echo "Storage status ... done" && df -h $(echo ${SHARE_DIRS} | tr '\n' ' ') | cut -c 40-
