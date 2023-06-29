#!/bin/bash

. ../../../generate.sh

VERSION=master
pull_repo $(pwd) performance benchmark-suite ljishen/BSFD ${VERSION} ${1}
rm -rf src/main/resources/benchmark-suite
mkdir -p src/main/resources/benchmark-suite &&
  cp -rvf ../../../.deps/performance/benchmark-suite src/main/resources
