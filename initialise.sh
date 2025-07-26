#!/bin/bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

################################################################################
# Setup network devices
################################################################################
cd "/Users/graham/Code/asystem/"
for i in {0..1}; do
  FAB_SKIP_GROUP_ALLBUT=$i FAB_SKIP_DELTA=true fab rel
  echo "" && echo "" && read -n 1 -s -r -p "Press any key to continue ... \n\n\n"
done

# reboot now
