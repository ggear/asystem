#!/usr/bin/env bash

declare -a HOST_ID=("2627" "5029" "27260")
declare -a HOST_NAME=("per1.speedtest.telstra.net" "nyc.speedtest.sbcglobal.net" "speedtest.ukbroadband.com")

VERBOSE=false
LATENCY=false
THROUGHPUT=false
RANDOM_THROUGHPUT=false

PING_FAIL=false
PING_ATTEMPTS=5
RANDOM_PERCENTAGE_POINT=25
HOST_COUNT=${#HOST_ID[@]}
PING_FAIL_FILE=/tmp/speedtest.failed
POSTURL="http://127.0.0.1:8091/rest/?sources=speedtest&targets="

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
      -v|--verbose)
      VERBOSE=true
      ;;
      -l|--latency)
      LATENCY=true
      ;;
      -t|--throughput)
      THROUGHPUT=true
      ;;
      -r|--random-throughput)
      RANDOM_THROUGHPUT=true
      ;;
      *)
      ;;
  esac
  shift
done

if ! ${LATENCY} && ! ${THROUGHPUT} && ! ${RANDOM_THROUGHPUT}; then
  echo "Usage: $0 [-v, --verbose] [-l, --latency] [-t, --throughput] [-r, --random-throughput]"
fi

if ${LATENCY} || ${THROUGHPUT}; then
  for (( i=0; i<${HOST_COUNT}; i++ )); do
    j=0
    PING=""
    while [ ! -n "${PING}" ]; do
      [ $j -eq ${PING_ATTEMPTS} ] && break;
      PING=$(ping -c 1 -t 30 ${HOST_NAME[$i]} | sed -ne '/.*time=/{;s///;s/ .*//;p;}' | tr -d '\n')
      ((j++))
    done
    JSON="{\"ping-icmp\":"${PING}",\"server\":{\"id\": \""${HOST_ID[$i]}"\"}}"
    ${VERBOSE} && echo -n "Latency ["${HOST_NAME[$i]}"]: " && echo -n ${JSON} && echo ""
    curl -H "Content-Type: application/json" -X POST -d "${JSON}" "${POSTURL}${HOST_ID[$i]}"
    if [ ! -n "${PING}" ]; then
      PING_FAIL=true
    fi
  done
fi

if ${PING_FAIL}; then
  touch ${PING_FAIL_FILE}
else
  [ -f ${PING_FAIL_FILE} ] && THROUGHPUT=true
  rm -rf ${PING_FAIL_FILE}
fi

if ${THROUGHPUT} || (${RANDOM_THROUGHPUT} && [ $(( ( RANDOM % 1000 )  + 1 )) -le ${RANDOM_PERCENTAGE_POINT} ]); then
  for (( i=0; i<${HOST_COUNT}; i++ )); do
    JSON=$(speedtest --json --bytes --timeout 30 --server ${HOST_ID[$i]} | tr '\n' ' ')
    ${VERBOSE} && echo -n "Throughput ["${HOST_NAME[$i]}"]: " && echo -n ${JSON} && echo ""
    curl -H "Content-Type: application/json" -X POST -d "${JSON}" "${POSTURL}${HOST_ID[$i]}"
    sleep 10
  done
fi
