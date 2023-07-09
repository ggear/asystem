#!/bin/bash

. ../../../generate.sh

VERSION=13.0.0
pull_repo $(pwd) tasmota tasmota-core arendst/tasmota v${VERSION} ${1}
mkdir -p src/build/resources/firmware &&
  rm -rf src/build/resources/firmware/*.gz &&
  wget -q -O src/build/resources/firmware/tasmota-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota.bin.gz &&
  wget -q -O src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota-minimal.bin.gz
