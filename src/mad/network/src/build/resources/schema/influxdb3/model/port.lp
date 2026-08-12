################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# ethernet/port [switch port health, one row per monitored port]
#   cadence 15m
#   tag module [always 'network']
#   tag port* [switch name and port index of the monitored port:
#     <string>]
#   field up - 15m [port link is live]
#   field speed_mbps Mbps 15m [negotiated link speed]
#   field full_duplex - 15m [port negotiated full duplex]
#   field degraded - 15m [port below expected speed or in half duplex]
#   field errors - 15m [link errors reported by the port this interval]

ethernet,
  module=network,
  port=<string>
    up=<0|1>,
    speed_mbps=<int>,
    full_duplex=<0|1>,
    degraded=<0|1>,
    errors=<int>
  <timestamp>
