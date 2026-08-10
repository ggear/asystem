################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/device [mesh device state reported by the coordinator, one row per paired device]
#   cadence 15m
#   tag device* [friendly name of the paired device]
#   entity <undeclared, whatever the service writes>
#   field available - 15m [device reporting available]
#   field coordinator - 15m [device is the coordinator itself]
#   field lqi - 15m [link quality reported for the device]
#   field weak - 15m [device link quality below the weak threshold]

zigbee,device=<device>
    available=<0|1>i,
    coordinator=<0|1>i,
    lqi=<number>i,
    weak=<0|1>i
    <timestamp>
