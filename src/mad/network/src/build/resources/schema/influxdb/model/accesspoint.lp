################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# wireless/accesspoint [access point health, one row per access point]
#   cadence 15m
#   tag module [always 'network']
#   tag accesspoint* [name of the access point:
#     uap-dar-hallway,
#     uap-dar-deck-north,
#     uap-dar-deck-south]
#   field up - 15m [device connected and seen by the controller recently]
#   field restarted - 15m [device came up since the previous check]
#   field overheating - 15m [controller flags the device as overheating]
#   field experience_pct % 15m [experience reported by the controller, capped by processor, memory and busiest link headroom]
#   field throughput_mbps Mbps 15m [traffic in both directions on the busiest link across the window]
#   field network_pct % 15m [busier direction of the busiest link against its negotiated speed across the window]
#   field clients - 15m [clients associated with the device, or for a gateway every client on the site]
#   field cpu_pct % 15m [processor in use]
#   field memory_pct % 15m [memory in use]

wireless,
  module=network,
  accesspoint=<string>
    up=<0|1>,
    restarted=<0|1>,
    overheating=<0|1>,
    experience_pct=<float>,
    throughput_mbps=<float>,
    network_pct=<float>,
    clients=<int>,
    cpu_pct=<float>,
    memory_pct=<float>
  <timestamp>
