#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

rm -rf src/main/resources/config/parse
mkdir -p src/main/resources/config/parse &&
  cp -rvf ${ROOT_DIR}/../../../.deps/performance/BSFD/benchmarks/sysbench/parse* src/main/resources/config/parse
for FILE in src/main/resources/config/parse/*.sh; do
  sed -i '' 's/grep/ggrep/g' ${FILE}
done

DIR_ROOT=src/test/resources/results/profiles/$(date +%F)
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

rm -rf ${DIR_ROOT} && mkdir -p ${DIR_ROOT}
for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  ssh -o StrictHostKeyChecking=no root@${HOST} /home/asystem/performance/benchmark.sh
  scp -r root@${HOST}:/home/asystem/performance/results ${DIR_ROOT}/${HOST}
  for TEST in cpu memory fileio; do
    for FILE in ${DIR_ROOT}/${HOST}/*_${TEST}_*.prof; do
      src/main/resources/config/parse/parse_${TEST}.sh src/test/resources/results/baseline/${HOST}/$(basename ${FILE}) ${FILE} ${DIR_ROOT}/profiles.csv
    done
  done
done