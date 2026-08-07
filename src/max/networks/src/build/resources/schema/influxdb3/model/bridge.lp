################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/bridge [coordinator state and the mesh it reports]
#   cadence 15m
#   field ok - 15m [coordinator online with its devices reachable]
#   field score - 15m [diagnosis score from 0 to 100]
#   field devices_total - 15m [devices paired with the coordinator]
#   field devices_ok - 15m [devices reporting available]
#   field devices_weak - 15m [devices with a link quality below the weak threshold]
#   field avg_lqi - 15m [mean link quality across the devices reporting one]

zigbee
    ok=<0|1>i,
    score=<number>i,
    devices_total=<number>i,
    devices_ok=<number>i,
    devices_weak=<number>i,
    avg_lqi=<number>
    <timestamp>
