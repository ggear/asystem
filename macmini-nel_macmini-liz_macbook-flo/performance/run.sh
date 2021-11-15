#!/bin/sh

################################################################################
# Bootstrap tests
################################################################################
DIR_RESULTS=/home/asystem/performance
rm -rf ${DIR_RESULTS} && mkdir -p ${DIR_RESULTS}
docker run --rm \
  ljishen/sysbench \
  /root/results/output_help.prof \
  help > /dev/null

################################################################################
# CPU tests
################################################################################
echo "################################################################################"
echo "# CPU tests ["$(hostname)"]"
echo "################################################################################"
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
echo "################################################################################"
echo "# Memory tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm \
  -v ${DIR_RESULTS}:/root/results \
  ljishen/sysbench \
  /root/results/output_memory.prof \
  --test=memory \
  run

################################################################################
# IO tests
################################################################################
echo "################################################################################"
echo "# IO tests ["$(hostname)"]"
echo "################################################################################"
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
echo "################################################################################"
docker run --rm \
  -v ${DIR_RESULTS}/workdir:/root/workdir \
  ljishen/sysbench \
  /root/results/output_fileio.prof \
  --test=fileio \
  cleanup > /dev/null
rm -rf ${DIR_RESULTS}/workdir
