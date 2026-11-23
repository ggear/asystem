################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# ethernet/powered [power drawn over ethernet, one row per device a monitored switch powers]
#   cadence 15m
#   tag module [always 'network']
#   tag powered* [name of the device on the powered port, or the switch and port name where no device is known:
#     <string>]
#   field power_w W 15m [power the device draws from its switch port]

ethernet,
  module=network,
  powered=<string>
    power_w=<float>
  <timestamp>
