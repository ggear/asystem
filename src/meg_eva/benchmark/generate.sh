#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

VERSION=master
pull_repo "${ROOT_DIR}" "${1}" benchmark benchmark-suite ljishen/BSFD "${VERSION}"
rm -rf ${ROOT_DIR}/src/main/resources/benchmark-suite
mkdir -p ${ROOT_DIR}/src/main/resources/benchmark-suite/benchmarks/sysbench &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/benchmark/benchmark-suite/benchmarks/sysbench ${ROOT_DIR}/src/main/resources/benchmark-suite/benchmarks
