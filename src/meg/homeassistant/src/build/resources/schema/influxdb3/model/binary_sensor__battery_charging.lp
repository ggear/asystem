################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__battery_charging [Home Assistant binary_sensor__battery_charging]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     kitchen_move_charging,
#     parents_move_charging]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__battery_charging,
  module=homeassistant,
  entity_id=<string>
    value=<float>
  <timestamp>
