#!/bin/bash

round_trip() {
  local topic="vernemq/gate/$$/${RANDOM}"
  {
    for _ in 1 2 3 4 5 6 7 8; do
      sleep 0.5
      timeout 2 mosquitto_pub -h 127.0.0.1 -p "${1}" -t "${topic}" -m ok >/dev/null 2>&1
    done
  } &
  local publisher=$!
  local received
  received="$(timeout 5 mosquitto_sub -h 127.0.0.1 -p "${1}" -t "${topic}" -C 1 2>/dev/null)"
  kill "${publisher}" 2>/dev/null
  wait "${publisher}" 2>/dev/null
  [[ "${received}" == "ok" ]]
}

open_listeners() {
  until round_trip 1884; do
    sleep 1
  done
  echo "vernemq gate round trip ok after [${SECONDS}s], settling [5s]"
  sleep 5
  until round_trip 1883 && (exec 3<>/dev/tcp/127.0.0.1/8080) 2>/dev/null; do
    vmq-admin listener start address=0.0.0.0 port=1883 --max_connections=10000 >/dev/null 2>&1
    vmq-admin listener start address=0.0.0.0 port=8080 --websocket --max_connections=10000 >/dev/null 2>&1
  done
  echo "vernemq gate public listeners open after [${SECONDS}s]"
}

export DOCKER_VERNEMQ_LISTENER__TCP__DEFAULT=127.0.0.1:1884
export DOCKER_VERNEMQ_LISTENER__WS__DEFAULT=127.0.0.1:8081
open_listeners &
exec start_vernemq
