################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# certs/home [certificate health across the monitored endpoints]
#   cadence 15m
#   field ok state 15m [every endpoint verified and none expiring inside the warning window]
#   field score count 15m [diagnosis score from 0 to 100]
#   field min_expiry_days days 15m [days until the nearest certificate expires]
#   field endpoints_total count 15m [endpoints monitored]
#   field endpoints_failed count 15m [endpoints unreachable or failing verification]

certs
    ok=<0|1>i,
    score=<number>i,
    min_expiry_days=<number>,
    endpoints_total=<number>i,
    endpoints_failed=<number>i
    <timestamp>
