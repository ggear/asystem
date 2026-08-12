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
#     dining_main_bulb_1,
#     dining_main_bulb_2,
#     dining_main_bulb_3,
#     dining_main_bulb_4,
#     dining_main_bulb_5,
#     dining_main_bulb_6,
#     edwin_night_light_bulb_1,
#     ensuite_main_bulb_1,
#     ensuite_sconces_bulb_1,
#     ensuite_sconces_bulb_2,
#     ensuite_sconces_bulb_3,
#     hallway_main_bulb_1,
#     hallway_main_bulb_2,
#     hallway_main_bulb_3,
#     hallway_main_bulb_4,
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
#     lounge_reading_bulb_1,
#     office_main_bulb_1,
#     pantry_main_bulb_1,
#     parents_main_bulb_1,
#     parents_main_bulb_2,
#     parents_main_bulb_3,
#     wardrobe_main_bulb_1]
#   field auto_update - <on-change> [Home Assistant value]
#   field display_precision - <on-change> [Home Assistant value]
#   field in_progress - <on-change> [Home Assistant value]
#   field installed_version - <on-change> [Home Assistant value]
#   field latest_version - <on-change> [Home Assistant value]
#   field release_summary_str - <on-change> [Home Assistant value]
#   field release_url_str - <on-change> [Home Assistant value]
#   field skipped_version_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field title_str - <on-change> [Home Assistant value]
#   field update_percentage - <on-change> [Home Assistant value]
#   field update_percentage_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

update__firmware,
  module=homeassistant,
  entity_id=<string>
    auto_update=<float>,
    display_precision=<float>,
    in_progress=<float>,
    installed_version=<float>,
    latest_version=<float>,
    update_percentage=<float>,
    value=<float>
  <timestamp>
