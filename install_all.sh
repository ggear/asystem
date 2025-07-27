#!/bin/bash
###############################################################################
# Install all modules
###############################################################################

install() {
  local start_index=$1
  local end_index=$2
  local last_index=0
  cd "/Users/graham/Code/asystem/" && echo "" && echo ""
  for i in $(seq ${start_index} ${end_index}); do
    service_name_csv=$(FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab cle | grep "CLEAN TRANSIENTS SUCCESSFUL" | cut -d' ' -f4 | cut -d'-' -f1,2 | paste -sd, - | sed 's/,/, /g' | tr ',' '\n' | sed 's/.*-\([^-, ]*\)$/\1/' | paste -sd', ' -)
    if [[ -n "${service_name_csv}" ]]; then
      last_index=${i}
      echo "Service Group [${i}] found [${service_name_csv}]"
    fi
  done
  echo "" && echo "" && echo -e "Press any key to install all services ... \n\n\n" && read -n 1 -s -r
  if [ "${last_index}" -gt 0 ]; then
    for i in $(seq ${start_index} ${last_index}); do
      FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab rel
      [[ $i != ${last_index} ]] && echo "" && echo "" && echo -e "Press any key to install next service ... \n\n\n" && read -n 1 -s -r
    done
  fi
}

if [ $# -eq 2 ]; then
  install "$1" "$2"
else
  install 0 9
  install 10 19
  install 20 29
fi
