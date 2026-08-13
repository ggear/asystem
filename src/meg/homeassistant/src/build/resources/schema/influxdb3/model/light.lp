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
#     deck_festoons_plug,
#     edwin_fan,
#     edwin_night_light,
#     edwin_night_light_bulb_1,
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
#     parents_main,
#     parents_main_bulb_1,
#     parents_main_bulb_2,
#     parents_main_bulb_3]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

light,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
