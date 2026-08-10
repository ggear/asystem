################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# diagnosis/plugin [health and diagnosis score of one network plugin]
#   cadence 15m
#   tag module [module the rows are written by, always [network]]
#   tag plugin* [name of the diagnosed plugin]
#   entity certificate, domain, ethernet, internet, weewx, wireless, zigbee
#   field ok - 15m [plugin reported a fit or sick diagnosis rather than dead]
#   field score - 15m [diagnosis score from 0 to 100]

diagnosis,module=network,plugin=<plugin>
    ok=<0|1>i,
    score=<number>i
    <timestamp>
