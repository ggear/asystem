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
  echo "" && read -n 1 -s -r -p "Press any key to continue ..."
done

FAB_SKIP_GROUP_ALLBUT=10 FAB_SKIP_DELTA=true fab rel
FAB_SKIP_GROUP_ALLBUT=11 FAB_SKIP_DELTA=true fab rel
FAB_SKIP_GROUP_ALLBUT=12 FAB_SKIP_DELTA=true fab rel

FAB_SKIP_GROUP_ALLBUT=13 FAB_SKIP_DELTA=true fab rel
FAB_SKIP_GROUP_ALLBUT=14 FAB_SKIP_DELTA=true fab rel
FAB_SKIP_GROUP_ALLBUT=15 FAB_SKIP_DELTA=true fab rel

# reboot now
