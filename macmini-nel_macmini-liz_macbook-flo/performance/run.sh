#!/bin/sh

################################################################################
# Bootstrap tests
################################################################################
DIR_RESULTS=/home/asystem/performance
rm -rf ${DIR_RESULTS} && mkdir -p ${DIR_RESULTS}
docker run --rm \
  ljishen/sysbench \
  /root/results/output_help.prof \
  help

################################################################################
# CPU tests
################################################################################
docker run --rm \
  -v ${DIR_RESULTS}:/root/results \
  ljishen/sysbench \
  /root/results/output_cpu.prof \
  --test=cpu \
  --cpu-max-prime=20000 \
  run

################################################################################
# Memory tests
################################################################################
docker run --rm \
  -v ${DIR_RESULTS}:/root/results \
  ljishen/sysbench \
  /root/results/output_memory.prof \
  --test=memory \
  run

################################################################################
# IO tests
################################################################################
docker run --rm \
  -v ${DIR_RESULTS}/workdir:/root/workdir \
  ljishen/sysbench \
  /root/results/output_fileio.prof \
  --test=fileio \
  --file-num=64 \
  prepare
docker run --rm \
  -v ${DIR_RESULTS}:/root/results \
  -v ${DIR_RESULTS}/workdir:/root/workdir \
  ljishen/sysbench \
  /root/results/output_fileio.prof \
  --test=fileio \
  --file-num=64 \
  --file-test-mode=seqrewr \
  run
docker run --rm \
  -v ${DIR_RESULTS}/workdir:/root/workdir \
  ljishen/sysbench \
  /root/results/output_fileio.prof \
  --test=fileio \
  cleanup
rm -r ${DIR_RESULTS}/workdir
