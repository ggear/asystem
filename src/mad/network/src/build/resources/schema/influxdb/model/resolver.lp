################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# domain/resolver [public DNS resolution of the monitored domain, one row per public resolver]
#   cadence 15m
#   tag module [always 'network']
#   tag resolver* [public DNS resolver queried:
#     cloudflare,
#     google,
#     quad9,
#     opendns,
#     adguard]
#   field ok - 15m [resolver agreed with the consensus address set]
#   field resolved - 15m [resolver returned an address]
#   field latency_ms ms 15m [time taken to resolve]

domain,
  module=network,
  resolver=<string>
    ok=<0|1>,
    resolved=<0|1>,
    latency_ms=<float>
  <timestamp>
