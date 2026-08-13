################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# fan [Home Assistant fan]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan,
#     deck_east_fan,
#     deck_fan,
#     deck_west_fan,
#     dining_air_purifier,
#     edwin_fan,
#     kitchen_fan_plug,
#     lounge_air_purifier,
#     lounge_fan,
#     parents_fan]
#   field direction_str - <on-change> [Home Assistant value]
#   field percentage - <on-change> [Home Assistant value]
#   field percentage_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

fan,
  module=homeassistant,
  entity_id=<string>
    direction_str=<text>,
    percentage=<float>,
    percentage_str=<text>,
    state=<text>,
    value=<float>
  <timestamp>
