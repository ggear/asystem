#!/bin/sh

rm -rf src/main/resources/scripts
mkdir -p src/main/resources/scripts &&
  cp -rvf ../../../asystem-external/performance/BSFD/benchmarks/sysbench/parse* src/main/resources/scripts

DIR_ROOT=src/test/resources/results/$(date +%F)
mkdir -p ${DIR_ROOT}
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
for HOST in ${HOSTS}; do
    scp -r root@${HOST}:/home/asystem/performance ${DIR_ROOT}/${HOST}
done
