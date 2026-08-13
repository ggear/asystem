################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__battery [Home Assistant sensor__battery]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock_battery,
#     back_door_sensor_battery,
#     front_door_lock_battery,
#     ipad_graham_battery_level,
#     iphone_graham_battery_level,
#     iphone_graham_watch_battery,
#     janes_ipad_battery_level,
#     janes_iphone_battery_level,
#     janes_iphone_battery_level_2,
#     janes_iphone_watch_battery_level,
#     kitchen_deck_battery,
#     kitchen_move_battery,
#     office_basement_battery,
#     office_dining_battery,
#     office_lounge_battery,
#     office_pantry_battery,
#     parents_move_battery,
#     pixel_tablet_battery_level,
#     pixel_tablet_battery_level_2,
#     tablet_ada_battery_level,
#     tablet_ada_battery_level_2,
#     tablet_edwin_battery_level_2]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     %]
#   field value - <on-change> [Home Assistant value]

sensor__battery,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=%
    value=<float>
  <timestamp>
