#!/bin/bash

. $(pwd)/../../generate.sh

pull_repo $(pwd) udmutilities udm-utilities ggear/udm-utilities 54f3bdab8a7cff7e11185a34bd32dff92a6dfa6f-ggear
rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../.deps/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities &&
  cp -rvf ../../.deps/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities &&
  cp -rvf ../../.deps/udmutilities/udm-utilities/cni-plugins src/main/resources/config/udm-utilities &&
  cp -rvf ../../.deps/udmutilities/udm-utilities/dns-common src/main/resources/config/udm-utilities &&
  cp -rvf ../../.deps/udmutilities/udm-utilities/run-pihole src/main/resources/config/udm-utilities
