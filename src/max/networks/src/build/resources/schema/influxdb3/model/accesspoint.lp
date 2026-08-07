################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# wireless/accesspoint [access point health across the wireless estate]
#   cadence 15m
#   field ok - 15m [every access point up with good client experience]
#   field score - 15m [diagnosis score from 0 to 100]
#   field aps_total - 15m [access points known to the controller]
#   field aps_ok - 15m [access points reporting up]
#   field avg_experience_pct % 15m [mean client experience across the access points that are up]

wireless
    ok=<0|1>i,
    score=<number>i,
    aps_total=<number>i,
    aps_ok=<number>i,
    avg_experience_pct=<number>
    <timestamp>
