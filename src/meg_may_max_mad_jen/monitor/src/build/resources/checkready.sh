OUTPUT="$(telegraf --test 2>/dev/null)" &&
  [ "$(grep -c '^> cpu,cpu=cpu-total,' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> mem,host=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> swap,host=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> disk,device=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> diskio,host=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> net,host=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> docker_container_cpu,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> docker_container_mem,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> docker_container_blkio,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
  [ "$(grep -c '^> docker_container_net,container_image=' <<<"${OUTPUT}")" -gt 0 ] &&
  telegraf --once >/dev/null 2>&1
