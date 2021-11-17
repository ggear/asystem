#!/bin/sh

################################################################################
# Bootstrap tests
################################################################################

DIR_RESULTS=/home/asystem/performance
NUM_THREADS=1
NUM_THREADS_MAX=4
MAX_RUNTIME_SEC=180
FILE_NUM=20
FILE_BLOCK_SIZE=32K
FILE_SIZE_TOTAL=6400000K
FILE_SIZE_TOTAL_VALIDATE=640000K

rm -rf ${DIR_RESULTS} && mkdir -p ${DIR_RESULTS}
docker run --rm ljishen/sysbench /root/results/output_help.prof help >/dev/null

################################################################################
# CPU tests
################################################################################
echo "################################################################################"
echo "# CPU tests ["$(hostname)"]"
echo "################################################################################"
docker run --rm -v ${DIR_RESULTS}:/root/results ljishen/sysbench /root/results/output_cpu.prof \
  --test=cpu \
  --num-threads=${NUM_THREADS_MAX} \
  --max-time=${MAX_RUNTIME_SEC} \
  --cpu-max-prime=80000 \
  run

#################################################################################
## Memory tests
#################################################################################
#echo "################################################################################"
#echo "# Memory tests ["$(hostname)"]"
#echo "################################################################################"
#docker run --rm -v ${DIR_RESULTS}:/root/results ljishen/sysbench /root/results/output_memory.prof \
#  --test=memory \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --memory-total-size=5G \
#  --memory-oper=read \
#  run
#docker run --rm -v ${DIR_RESULTS}:/root/results ljishen/sysbench /root/results/output_memory.prof \
#  --test=memory \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --memory-total-size=5G \
#  --memory-oper=write \
#  run
#
#################################################################################
## IO tests
#################################################################################
#echo "################################################################################"
#echo "# Sequential IO tests ["$(hostname)"]"
#echo "################################################################################"
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_prepare.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL} \
#  --file-test-mode=seqrewr \
#  prepare
#docker run --rm -v ${DIR_RESULTS}:/root/results -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_seqrewr.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL} \
#  --file-test-mode=seqrewr \
#  run
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_cleanup.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  cleanup >/dev/null
#
#echo "################################################################################"
#echo "# Random IO tests ["$(hostname)"]"
#echo "################################################################################"
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_prepare.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL} \
#  --file-test-mode=rndrw \
#  prepare
#docker run --rm \
#  -v ${DIR_RESULTS}:/root/results -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_rndrw.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL} \
#  --file-rw-ra=1.5 \
#  --file-test-mode=rndrw \
#  run
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_cleanup.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  cleanup >/dev/null
#
#echo "################################################################################"
#echo "# Validate IO tests ["$(hostname)"]"
#echo "################################################################################"
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_prepare.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL_VALIDATE} \
#  --validate=on\
#  --file-test-mode=rndrw \
#  prepare
#docker run --rm \
#  -v ${DIR_RESULTS}:/root/results -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_rndrw.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  --file-num=${FILE_NUM} \
#  --file-block-size=${FILE_BLOCK_SIZE} \
#  --file-total-size=${FILE_SIZE_TOTAL_VALIDATE} \
#  --file-rw-ra=1.5 \
#  --validate=on\
#  --file-test-mode=rndrw \
#  run
#docker run --rm -v ${DIR_RESULTS}/workdir:/root/workdir ljishen/sysbench /root/results/output_fileio_cleanup.prof \
#  --test=fileio \
#  --num-threads=${NUM_THREADS} \
#  --max-time=${MAX_RUNTIME_SEC} \
#  cleanup >/dev/null
#echo "################################################################################"
#rm -rf ${DIR_RESULTS}/workdir
