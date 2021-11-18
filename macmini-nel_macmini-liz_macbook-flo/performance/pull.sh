#!/bin/sh

rm -rf src/main/resources/config/parse*
mkdir -p src/main/resources/config &&
  cp -rvf ../../../asystem-external/performance/BSFD/benchmarks/sysbench/parse* src/main/resources/config

DIR_ROOT=src/test/resources/results/$(date +%F)
rm -rf ${DIR_ROOT} && mkdir -p ${DIR_ROOT}
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
for HOST in ${HOSTS}; do
    scp -r root@${HOST}:/home/asystem/performance ${DIR_ROOT}/${HOST}
done
