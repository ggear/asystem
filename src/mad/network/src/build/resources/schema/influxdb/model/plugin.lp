################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# diagnosis/plugin [health and diagnosis score of one network plugin]
#   cadence 15m
#   tag module [always 'network']
#   tag plugin* [name of the diagnosed plugin:
#     certificate,
#     domain,
#     ethernet,
#     internet,
#     weewx,
#     wireless,
#     zigbee]
#   field ok - 15m [plugin reported a fit or sick diagnosis rather than dead]
#   field score - 15m [diagnosis score from 0 to 100]

diagnosis,
  module=network,
  plugin=<string>
    ok=<0|1>,
    score=<int>
  <timestamp>
