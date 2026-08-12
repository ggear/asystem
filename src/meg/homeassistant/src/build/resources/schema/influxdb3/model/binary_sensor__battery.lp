################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__battery [Home Assistant binary_sensor__battery]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock_battery_low,
#     back_door_sensor_battery_low,
#     front_door_lock_battery_low]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__battery,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
