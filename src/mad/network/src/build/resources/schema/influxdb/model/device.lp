################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/device [mesh device state reported by the coordinator, one row per paired device]
#   cadence 15m
#   tag module [always 'network']
#   tag device* [friendly name of the paired device:
#     <string>]
#   field available - 15m [device reporting available]
#   field lqi - 15m [median link quality across the window while available]
#   field weak - 15m [device median link quality below the weak threshold]
#   field last_seen_s s 15m [age of the device's latest report]

zigbee,
  module=network,
  device=<string>
    available=<0|1>,
    lqi=<int>,
    weak=<0|1>,
    last_seen_s=<int>
  <timestamp>
