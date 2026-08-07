################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# internet/gateway [internet reachability through the local gateway and the public ping targets]
#   cadence 15m
#   field ok - 15m [gateway up and the public targets reachable within normal range]
#   field score - 15m [diagnosis score from 0 to 100]
#   field targets_total - 15m [public targets pinged]
#   field targets_ok - 15m [public targets answering across the window]
#   field avg_loss_pct % 15m [mean packet loss across the public targets]
#   field avg_rtt_ms ms 15m [mean round trip time across the public targets]
#   field avg_jitter_ms ms 15m [mean jitter across the public targets]
#   field gateway_ok - 15m [the local gateway answered at least one ping in the window]

internet
    ok=<0|1>i,
    score=<number>i,
    targets_total=<number>i,
    targets_ok=<number>i,
    avg_loss_pct=<number>,
    avg_rtt_ms=<number>,
    avg_jitter_ms=<number>,
    gateway_ok=<0|1>i
    <timestamp>
