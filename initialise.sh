#!/bin/bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

################################################################################
# Setup network devices
################################################################################

initialise() {
  local start=$1
  local end=$2
  local rel_end=0
  cd "/Users/graham/Code/asystem/"
  for i in $(seq ${start} ${end}); do
    SERVICES=$(FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab cle | grep "CLEAN TRANSIENTS SUCCESSFUL" | cut -d' ' -f4 | cut -d'-' -f1,2 | paste -sd, - | sed 's/,/, /g' | tr ',' '\n' | sed 's/.*-\([^-, ]*\)$/\1/' | paste -sd', ' -)
    if [[ -n "${SERVICES}" ]]; then
      rel_end=${i}
      echo "Service Group [${i}] found [${SERVICES}]"
    fi
  done
  if [ "${rel_end}" -gt 0 ]; then
    for i in $(seq ${start} ${rel_end}); do
      FAB_SKIP_GROUP_ALLBUT=${i} FAB_SKIP_DELTA=true fab rel
      echo "" && echo "" && echo -e "Press any key to continue ... \n\n\n" && read -n 1 -s -r
    done
  fi
}

initialise 1 9
