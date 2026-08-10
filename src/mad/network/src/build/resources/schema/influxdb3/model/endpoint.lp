################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# certificate/endpoint [certificate health, one row per monitored endpoint]
#   cadence 15m
#   tag endpoint* [monitored TLS endpoint]
#   entity home.janeandgraham.com:443
#   field verified - 15m [endpoint reachable and its certificate verified]
#   field expiry_days d 15m [days until the certificate expires]
#   field validity_pct % 15m [share of the certificate lifetime still remaining]

certificate,endpoint=<endpoint>
    verified=<0|1>i,
    expiry_days=<number>,
    validity_pct=<number>
    <timestamp>
