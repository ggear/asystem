################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/router [the coordinator and the always on outlets routing the mesh, one row per key device]
#   cadence 15m
#   tag module [always 'network']
#   tag router* [coordinator, or the friendly name of a routing outlet:
#     Coordinator,
#     Ada Desk Outlet,
#     Deck Fans Outlet,
#     Edwin Desk Outlet,
#     Kitchen Fan Outlet]
#   field available - 15m [coordinator online, or router reporting available]
#   field lqi - 15m [router median link quality across the window while available]

zigbee,
  module=network,
  router=<string>
    available=<0|1>,
    lqi=<int>
  <timestamp>
