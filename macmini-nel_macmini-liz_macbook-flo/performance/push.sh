#!/bin/sh

rm -rf src/main/resources/config/parse
mkdir -p src/main/resources/config/parse &&
  cp -rvf ../../.deps/performance/BSFD/benchmarks/sysbench/parse* src/main/resources/config/parse
for FILE in src/main/resources/config/parse/*.sh; do
  sed -i '' 's/grep/ggrep/g' ${FILE}
done

DIR_ROOT=src/test/resources/results/profiles/$(date +%F)
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

rm -rf ${DIR_ROOT} && mkdir -p ${DIR_ROOT}
for HOST in ${HOSTS}; do
  DIR_ROOT_HOST=$(ssh root@macbook-flo "find /home/asystem/performance -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
  ssh -o StrictHostKeyChecking=no root@${HOST} ${DIR_ROOT_HOST}/benchmark.sh
  scp -r root@${HOST}:${DIR_ROOT_HOST}/results ${DIR_ROOT}/${HOST}
  for TEST in cpu memory fileio; do
    for FILE in $(ls ${DIR_ROOT}/${HOST}/*_${TEST}_*.prof); do
      src/main/resources/config/parse/parse_${TEST}.sh src/test/resources/results/baseline/${HOST}/$(basename ${FILE}) ${FILE} ${DIR_ROOT}/profiles.csv
    done
  done

done
