#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

${ROOT_DIR}/src/main/resources/config/udm-certificates/certs.sh pull ${HOST_LETSENCRYPT} ${HOST}

VERSION=ggear-patch-1
pull_repo $(pwd) udmutilities udm-utilities ggear/udm-utilities ${VERSION} ${1}
rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities

# INFO: Disable podman services since it has been deprecated since udm-pro-3
#mkdir -p src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/cni-plugins src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/dns-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/run-pihole src/main/resources/config/udm-utilities
