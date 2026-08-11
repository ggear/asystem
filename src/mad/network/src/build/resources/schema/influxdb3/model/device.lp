################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/device [mesh device state reported by the coordinator, one row per paired device]
#   cadence 15m
#   tag module [always 'network']
#   tag device* [friendly name of the paired device:
#     <string>]
#   field available - 15m [device reporting available]
#   field coordinator - 15m [device is the coordinator itself]
#   field lqi - 15m [link quality reported for the device]
#   field weak - 15m [device link quality below the weak threshold]

zigbee,
  module=network,
  device=<device>
    available=<0|1>,
    coordinator=<0|1>,
    lqi=<int>,
    weak=<0|1>
  <timestamp>
