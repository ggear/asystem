#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# NOTES: https://github.com/ljishen/BSFD/commits/master
VERSION=master
pull_repo "${ROOT_DIR}" "${1}" "benchmark" "benchmark-suite" "ljishen/BSFD" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/benchmark/benchmark-suite/benchmarks/sysbench" "${ROOT_DIR}/src/main/resources/benchmark-suite/benchmarks/sysbench" || exit $?
