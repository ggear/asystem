#!/bin/bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

################################################################################
# Setup network devices
################################################################################

initialise() {
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
  echo "" && echo "" && echo -e "Press any key to release all services ... \n\n\n" && read -n 1 -s -r
  if [ "${last_index}" -gt 0 ]; then
    for i in $(seq ${start_index} ${last_index}); do
      FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab rel
      echo "" && echo "" && echo -e "Press any key to release next service ... \n\n\n" && read -n 1 -s -r
    done
  fi
}

initialise 0 9
