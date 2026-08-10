################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# light [Home Assistant light]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan,
#     ada_lamp,
#     ada_lamp_bulb_1,
#     bathroom_main,
#     bathroom_main_bulb_1,
#     deck_festoons_plug,
#     dining_main,
#     dining_main_bulb_1,
#     dining_main_bulb_2,
#     dining_main_bulb_3,
#     dining_main_bulb_4,
#     dining_main_bulb_5,
#     dining_main_bulb_6,
#     edwin_fan,
#     edwin_night_light,
#     edwin_night_light_bulb_1,
#     ensuite_main,
#     ensuite_main_bulb_1,
#     hallway_sconces,
#     hallway_sconces_bulb_1,
#     hallway_sconces_bulb_2,
#     kitchen_bench_lights_plug,
#     kitchen_main,
#     kitchen_main_bulb_1,
#     kitchen_main_bulb_2,
#     kitchen_main_bulb_3,
#     kitchen_main_bulb_4,
#     landing_festoons_plug,
#     lounge_fan,
#     lounge_lamp,
#     lounge_lamp_bulb_1,
#     lounge_main,
#     lounge_main_bulb_1,
#     lounge_main_bulb_2,
#     lounge_main_bulb_3,
#     office_main,
#     office_main_bulb_1,
#     pantry_main,
#     pantry_main_bulb_1,
#     parents_main,
#     parents_main_bulb_1,
#     parents_main_bulb_2,
#     parents_main_bulb_3]
#   field assumed_state - <on-change> [Home Assistant value]
#   field brightness - <on-change> [Home Assistant value]
#   field brightness_str - <on-change> [Home Assistant value]
#   field effect_list_str - <on-change> [Home Assistant value]
#   field effect_str - <on-change> [Home Assistant value]
#   field group_entities_str - <on-change> [Home Assistant value]
#   field max_color_temp_kelvin - <on-change> [Home Assistant value]
#   field min_color_temp_kelvin - <on-change> [Home Assistant value]
#   field rgb_color - <on-change> [Home Assistant value]
#   field rgb_color_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

light,
  module=homeassistant,
  entity_id=<string>
    assumed_state=<float>,
    brightness=<float>,
    max_color_temp_kelvin=<float>,
    min_color_temp_kelvin=<float>,
    rgb_color=<float>,
    value=<float>
  <timestamp>
