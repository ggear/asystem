#!/bin/bash
###############################################################################
# Install all modules
###############################################################################

install_all() {
  local start_index=$1
  local end_index=$2
  local last_index=${start_index}
  local list_only=${3:-true}
  cd "/Users/graham/Code/asystem/"
  for i in $(seq ${start_index} ${end_index}); do
    service_name_csv=$(
      FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab cle |
        grep "CLEAN TRANSIENTS SUCCESSFUL" | cut -d' ' -f4 | cut -d'-' -f1,2 | paste -sd, - |
        sed 's/,/, /g' | tr ',' '\n' | sed 's/.*-\([^-, ]*\)$/\1/' | paste -sd', ' -
    )
    if [[ -n "${service_name_csv}" ]]; then
      last_index=${i}
      echo "Service Group [$(printf "%02d" ${i})] found services [${service_name_csv}]"
    fi
  done
  if [ "${list_only}" = false ]; then
    echo "" && echo "" && echo -e "Press any key to install all services ... \n\n\n" && read -n 1 -s -r
    if [ "${last_index}" -gt 0 ]; then
      for i in $(seq ${start_index} ${last_index}); do
        FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab rel
        [[ $i != ${last_index} ]] && echo "" && echo "" && echo -e "Press any key to install next service ... \n\n\n" && read -n 1 -s -r
      done
    fi
  fi
}

if [ $# -eq 2 ]; then
  install_all "$1" "$2" false
else
  install_all 0 9
  install_all 10 19
  install_all 20 29
fi
