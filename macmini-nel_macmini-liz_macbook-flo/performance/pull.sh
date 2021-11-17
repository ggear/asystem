#!/bin/sh

rm -rf src/test/resources/scripts
mkdir -p src/test/resources/scripts &&
  cp -rvf ../../../asystem-external/performance/BSFD/benchmarks/sysbench/parse* src/test/resources/scripts

DIR_ROOT=src/test/resources/results/$(date +%F)
rm -rf ${DIR_ROOT} && mkdir -p ${DIR_ROOT}
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
for HOST in ${HOSTS}; do
    scp -r root@${HOST}:/home/asystem/performance ${DIR_ROOT}/${HOST}
done
