################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# wireless/accesspoint [access point health, one row per access point]
#   cadence 15m
#   tag module [module the rows are written by, always [network]]
#   tag accesspoint* [name of the access point]
#   entity <undeclared, whatever the service writes>
#   field up - 15m [access point reporting up]
#   field experience_pct % 15m [client experience reported by the access point]
#   field clients - 15m [clients associated with the access point]

wireless,module=network,accesspoint=<accesspoint>
    up=<0|1>i,
    experience_pct=<number>,
    clients=<number>i
    <timestamp>
