#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

ssh root@${HOST} "cd ${INSTALL}; echo '---' && echo -n 'Stopping container ... ' && docker stop $(basename ${ROOT_DIR}) && echo '---' && sleep 1"
ssh root@${HOST} "rm -rvf ${HOME}/custom_components && rm -rvf ${HOME}/custom_packages && rm -rvf ${HOME}/ui-lovelace && rm -rvf ${HOME}/www"
scp -r ${ROOT_DIR}/src/main/resources/data/* root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL}; echo '---' && echo -n 'Starting container ... ' && docker start $(basename ${ROOT_DIR}) && echo '---' && sleep 1 && docker logs -f $(basename ${ROOT_DIR})"
