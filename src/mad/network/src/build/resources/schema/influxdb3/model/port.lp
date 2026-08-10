################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# ethernet/port [switch port health, one row per monitored port]
#   cadence 15m
#   tag module [module the rows are written by, always [network]]
#   tag port* [switch name and port index of the monitored port]
#   entity <undeclared, whatever the service writes>
#   field up - 15m [port link is live]
#   field speed_mbps Mbps 15m [negotiated link speed]
#   field full_duplex - 15m [port negotiated full duplex]
#   field degraded - 15m [port below expected speed or in half duplex]
#   field errors - 15m [link errors reported by the port this interval]

ethernet,module=network,port=<port>
    up=<0|1>i,
    speed_mbps=<number>i,
    full_duplex=<0|1>i,
    degraded=<0|1>i,
    errors=<number>i
    <timestamp>
