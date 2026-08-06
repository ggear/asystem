################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# ethernet/ports [switch port health across the monitored ports]
#   cadence 15m
#   field score count 15m [diagnosis score from 0 to 100]
#   field ok state 15m [every monitored port up at expected speed with no link errors]
#   field ports_total count 15m [monitored ports]
#   field ports_ok count 15m [monitored ports with a live link]
#   field ports_degraded count 15m [ports below expected speed or in half duplex]
#   field ports_errored count 15m [ports reporting link errors this interval]

ethernet
    score=<number>i,
    ok=<0|1>i,
    ports_total=<number>i,
    ports_ok=<number>i,
    ports_degraded=<number>i,
    ports_errored=<number>i
    <timestamp>
