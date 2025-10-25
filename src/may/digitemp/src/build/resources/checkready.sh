true

#OUTPUT="$(telegraf --test 2>/dev/null)" &&
#  [ "$(grep -c '^> cpu,cpu=cpu-total,' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> mem,host=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> swap,host=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> disk,device=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> diskio,host=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> net,host=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> docker_container_cpu,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> docker_container_mem,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> docker_container_blkio,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
#  [ "$(grep -c '^> docker_container_net,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
#  telegraf --once >/dev/null 2>&1

#telegraf --once >/dev/null 2>&1 &&
#  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .tags.run_code) -eq 0 ] &&
#  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_failed) -eq 0 ] &&
#  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_succeeded) -eq 3 ]
