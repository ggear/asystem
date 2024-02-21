#!/bin/bash

telegraf --once >/dev/null 2>&1 &&
  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .tags.run_code) -eq 0 ] &&
  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_failed) -eq 0 ] &&
  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_succeeded) -eq 3 ]
