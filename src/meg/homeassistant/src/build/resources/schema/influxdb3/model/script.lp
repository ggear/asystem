################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# script [Home Assistant script]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     home_secure_back_door_off,
#     home_sleep_off,
#     home_sleep_on]
#   field last_triggered - <on-change> [Home Assistant value]
#   field last_triggered_str - <on-change> [Home Assistant value]
#   field max - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

script,
  module=homeassistant,
  entity_id=<string>
    last_triggered=<float>,
    max=<float>,
    value=<float>
  <timestamp>
