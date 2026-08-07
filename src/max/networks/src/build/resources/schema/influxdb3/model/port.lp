################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# ethernet/port [switch port health across the monitored ports]
#   cadence 15m
#   field score - 15m [diagnosis score from 0 to 100]
#   field ok - 15m [every monitored port up at expected speed with no link errors]
#   field ports_total - 15m [monitored ports]
#   field ports_ok - 15m [monitored ports with a live link]
#   field ports_degraded - 15m [ports below expected speed or in half duplex]
#   field ports_errored - 15m [ports reporting link errors this interval]

ethernet
    score=<number>i,
    ok=<0|1>i,
    ports_total=<number>i,
    ports_ok=<number>i,
    ports_degraded=<number>i,
    ports_errored=<number>i
    <timestamp>
