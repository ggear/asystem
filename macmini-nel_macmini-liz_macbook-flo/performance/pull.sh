#!/bin/sh

rm -rf src/main/resources/config/parse
mkdir -p src/main/resources/config/parse &&
  cp -rvf ../../../asystem-external/performance/BSFD/benchmarks/sysbench/parse* src/main/resources/config/parse

DIR_ROOT=src/test/resources/results/$(date +%F)
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
rm -rf ${DIR_ROOT} && mkdir -p ${DIR_ROOT}
for HOST in ${HOSTS}; do
    DIR_ROOT_HOST=$(ssh root@macbook-flo "find /home/asystem/performance -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1")
    ssh -o StrictHostKeyChecking=no root@${HOST} ${DIR_ROOT_HOST}/benchmark.sh
    scp -r root@${HOST}:${DIR_ROOT_HOST}/results ${DIR_ROOT}/${HOST}
done
