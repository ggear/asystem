#!/bin/sh

################################################################################
# Bootstrap tests
################################################################################

RESULTS_DIR=/home/asystem/performance/latest/results
NUM_THREADS=1
NUM_THREADS_MAX=4
MAX_RUNTIME_SEC=180
FILE_NUM=20
FILE_BLOCK_SIZE=32K
FILE_SIZE_TOTAL=6400000K
FILE_SIZE_TOTAL_VALIDATE=640000K

rm -rf ${RESULTS_DIR} && mkdir -p ${RESULTS_DIR}
[ $(docker ps -a -q | wc -l) -gt 0 ] && docker stop $(docker ps -q)
docker run --rm ljishen/sysbench /root/results/help.prof help >/dev/null

################################################################################
# CPU tests
################################################################################
echo "################################################################################"
echo "# CPU tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${RESULTS_DIR}:/root/results ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_cpu_maxprime-20000.prof \
  --test=cpu \
  --num-threads=${NUM_THREADS_MAX} \
  --max-time=${MAX_RUNTIME_SEC} \
  --cpu-max-prime=20000 \
  run

#################################################################################
## Memory tests
#################################################################################
echo "################################################################################"
echo "# Memory tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${RESULTS_DIR}:/root/results ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_memory_read-5G.prof \
  --test=memory \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --memory-total-size=5G \
  --memory-oper=read \
  run
docker run --rm -v ${RESULTS_DIR}:/root/results ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_memory_write-5G.prof \
  --test=memory \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --memory-total-size=5G \
  --memory-oper=write \
  run

################################################################################
# IO tests
################################################################################
echo "################################################################################"
echo "# Sequential IO tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_prepare.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL} \
  --file-test-mode=seqrewr \
  prepare
docker run --rm -v ${RESULTS_DIR}:/root/results -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_seqrewr-${FILE_SIZE_TOTAL}.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL} \
  --file-test-mode=seqrewr \
  run
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_cleanup.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  cleanup >/dev/null

echo "################################################################################"
echo "# Random IO tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_prepare.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL} \
  --file-test-mode=rndrw \
  prepare
docker run --rm \
  -v ${RESULTS_DIR}:/root/results -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_rndrw-${FILE_SIZE_TOTAL}.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL} \
  --file-rw-ra=1.5 \
  --file-test-mode=rndrw \
  run
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_cleanup.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  cleanup >/dev/null

echo "################################################################################"
echo "# Validate IO tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_prepare.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL_VALIDATE} \
  --validate=on\
  --file-test-mode=rndrw \
  prepare
docker run --rm \
  -v ${RESULTS_DIR}:/root/results -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_rndrw-validate-${FILE_SIZE_TOTAL}.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  --file-num=${FILE_NUM} \
  --file-block-size=${FILE_BLOCK_SIZE} \
  --file-total-size=${FILE_SIZE_TOTAL_VALIDATE} \
  --file-rw-ra=1.5 \
  --validate=on\
  --file-test-mode=rndrw \
  run
docker run --rm -v ${RESULTS_DIR}/workdir:/root/workdir ljishen/sysbench /root/results/${MAX_RUNTIME_SEC}s_$(hostname)_fileio_cleanup.prof \
  --test=fileio \
  --num-threads=${NUM_THREADS} \
  --max-time=${MAX_RUNTIME_SEC} \
  cleanup >/dev/null
echo "################################################################################"
rm -rf ${RESULTS_DIR}/workdir
