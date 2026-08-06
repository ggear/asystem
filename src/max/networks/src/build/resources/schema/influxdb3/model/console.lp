################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# weewx/console [the weather station console link and its health]
#   cadence 15m
#   field ok state 15m [console reporting a fresh pulse with usable signal quality]
#   field score count 15m [diagnosis score from 0 to 100]

weewx
    ok=<0|1>i,
    score=<number>i
    <timestamp>
