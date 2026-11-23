################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# weewx/console [weather station console link health, one row per console]
#   cadence 15m
#   tag module [always 'network']
#   tag console* [name of the weather station console:
#     weatherstation]
#   field fresh - 15m [console reported a pulse inside the freshness window]
#   field quality_pct % 15m [console coms signal quality]

weewx,
  module=network,
  console=weatherstation
    fresh=<0|1>,
    quality_pct=<float>
  <timestamp>
