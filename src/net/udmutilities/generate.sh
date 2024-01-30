#!/bin/bash

. ../../../generate.sh

VERSION=ggear-patch-1
pull_repo $(pwd) udmutilities udm-utilities ggear/udm-utilities ${VERSION} ${1}
rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities

# INFO: Disable pihole since upgrading to udm-pro-3 and the deprecation of podman
#mkdir -p src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/cni-plugins src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/dns-common src/main/resources/config/udm-utilities &&
#  cp -rvf ../../../.deps/udmutilities/udm-utilities/run-pihole src/main/resources/config/udm-utilities
