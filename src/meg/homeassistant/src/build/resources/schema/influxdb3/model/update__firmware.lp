################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# update__firmware [Home Assistant update__firmware]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_desk_outlet,
#     ada_lamp_bulb_1,
#     bathroom_main_bulb_1,
#     deck_fans_outlet,
#     dining_air_purifier,
#     edwin_night_light_bulb_1,
#     ensuite_main_bulb_1,
#     hallway_sconces_bulb_1,
#     hallway_sconces_bulb_2,
#     kitchen_fan_outlet,
#     kitchen_main_bulb_1,
#     kitchen_main_bulb_2,
#     kitchen_main_bulb_3,
#     kitchen_main_bulb_4,
#     laundry_main_bulb_1,
#     lounge_air_purifier,
#     lounge_lamp_bulb_1,
#     lounge_main_bulb_1,
#     lounge_main_bulb_2,
#     lounge_main_bulb_3,
#     office_main_bulb_1,
#     pantry_main_bulb_1,
#     parents_main_bulb_1,
#     parents_main_bulb_2,
#     parents_main_bulb_3]
#   field installed_version - <on-change> [Home Assistant value]
#   field latest_version - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

update__firmware,
  module=homeassistant,
  entity_id=<string>
    installed_version=<float>,
    latest_version=<float>,
    state=<text>,
    value=<float>
  <timestamp>
