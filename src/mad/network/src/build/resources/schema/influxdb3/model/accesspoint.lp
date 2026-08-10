################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# wireless/accesspoint [access point health, one row per access point]
#   cadence 15m
#   tag module [always 'network']
#   tag accesspoint* [name of the access point:
#     <string>]
#   field up - 15m [access point reporting up]
#   field experience_pct % 15m [client experience reported by the access point]
#   field clients - 15m [clients associated with the access point]

wireless,
  module=network,
  accesspoint=<string>
    up=<0|1>,
    experience_pct=<float>,
    clients=<int>
  <timestamp>
