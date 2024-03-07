#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

VERSION=ggear-patch-1
pull_repo $(pwd) udmutilities udm-utilities ggear/udm-utilities ${VERSION} ${1}
rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities

${ROOT_DIR}/src/main/resources/config/certs.sh pull

# INFO: Disable podman services since it has been deprecated since udm-pro-3
#mkdir -p src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/cni-plugins src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/dns-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/run-pihole src/main/resources/config/udm-utilities
