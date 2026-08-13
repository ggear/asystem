################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__occupancy [Home Assistant binary_sensor__occupancy]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan_occupancy,
#     deck_east_fan_occupancy,
#     deck_west_fan_occupancy,
#     edwin_fan_occupancy,
#     lounge_fan_occupancy,
#     parents_fan_occupancy]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__occupancy,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
