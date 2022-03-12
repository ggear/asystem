#!/bin/sh

rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/on-boot-script src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/container-common src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/cni-plugins src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/dns-common src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities/run-pihole src/main/resources/config/udm-utilities

rm -rf src/main/resources/config/udm-host-records
mkdir -p src/main/resources/config/udm-host-records &&
  cp -rvf ../../../asystem-external/udmutilities/udm-host-records src/main/resources/config &&
  rm -rf src/main/resources/config/udm-host-records/.git*
