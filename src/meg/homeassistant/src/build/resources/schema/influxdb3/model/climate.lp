################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# climate [Home Assistant climate]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan_auto_comfort,
#     deck_east_fan_auto_comfort,
#     deck_west_fan_auto_comfort,
#     edwin_fan_auto_comfort,
#     lounge_fan_auto_comfort,
#     parents_fan_auto_comfort]
#   field current_temperature - <on-change> [Home Assistant value]
#   field hvac_action_str - <on-change> [Home Assistant value]
#   field hvac_modes_str - <on-change> [Home Assistant value]
#   field max_temp - <on-change> [Home Assistant value]
#   field min_temp - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field temperature - <on-change> [Home Assistant value]

climate,
  module=homeassistant,
  entity_id=<ada_fan_auto_comfort|deck_east_fan_auto_comfort|deck_west_fan_auto_comfort|edwin_fan_auto_comfort|lounge_fan_auto_comfort|parents_fan_auto_comfort>
    current_temperature=<float>,
    max_temp=<float>,
    min_temp=<float>,
    temperature=<float>
  <timestamp>
