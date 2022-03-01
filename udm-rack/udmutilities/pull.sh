#!/bin/sh

rm -rf src/main/resources/config/udm-utilities
mkdir -p src/main/resources/config/udm-utilities &&
  cp -rvf ../../../asystem-external/udmutilities/udm-utilities src/main/resources/config &&
  rm -rf src/main/resources/config/udm-utilities/.github
