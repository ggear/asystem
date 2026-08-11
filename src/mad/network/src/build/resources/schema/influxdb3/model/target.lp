################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# internet/target [internet reachability, one row per ping target]
#   cadence 15m
#   tag module [always 'network']
#   tag target* [ping target, either the local gateway or a public address:
#     gateway,
#     1.1.1.1,
#     8.8.8.8,
#     9.9.9.9]
#   field reachable - 15m [target answered at least one ping across the window]
#   field loss_pct % 15m [packet loss across the window]
#   field rtt_ms ms 15m [mean round trip time across the window]
#   field jitter_ms ms 15m [mean jitter across the window]

internet,
  module=network,
  target=<gateway|1.1.1.1|8.8.8.8|9.9.9.9>
    reachable=<0|1>,
    loss_pct=<float>,
    rtt_ms=<float>,
    jitter_ms=<float>
  <timestamp>
