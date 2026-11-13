################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__duration [Home Assistant sensor__duration]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     rackmains_battery_age_days,
#     rackmains_guard_battery_seconds,
#     rackmains_guard_mains_seconds]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     d,
#     s]
#   field value - <on-change> [Home Assistant value]

sensor__duration,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    value=<float>
  <timestamp>
