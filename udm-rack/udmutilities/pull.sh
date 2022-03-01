#!/bin/sh

rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities
