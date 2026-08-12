################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__timestamp [Home Assistant sensor__timestamp]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bom_darlington_astronomical_sunrise_time_0,
#     bom_darlington_astronomical_sunrise_time_1,
#     bom_darlington_astronomical_sunrise_time_2,
#     bom_darlington_astronomical_sunrise_time_3,
#     bom_darlington_astronomical_sunrise_time_4,
#     bom_darlington_astronomical_sunrise_time_5,
#     bom_darlington_astronomical_sunrise_time_6,
#     bom_darlington_astronomical_sunrise_time_7,
#     bom_darlington_astronomical_sunset_time_0,
#     bom_darlington_astronomical_sunset_time_1,
#     bom_darlington_astronomical_sunset_time_2,
#     bom_darlington_astronomical_sunset_time_3,
#     bom_darlington_astronomical_sunset_time_4,
#     bom_darlington_astronomical_sunset_time_5,
#     bom_darlington_astronomical_sunset_time_6,
#     bom_darlington_astronomical_sunset_time_7,
#     bom_darlington_uv_end_time_0,
#     bom_darlington_uv_end_time_1,
#     bom_darlington_uv_end_time_2,
#     bom_darlington_uv_end_time_3,
#     bom_darlington_uv_start_time_0,
#     bom_darlington_uv_start_time_1,
#     bom_darlington_uv_start_time_2,
#     bom_darlington_uv_start_time_3,
#     deck_fans_outlet_last_seen,
#     kitchen_fan_outlet_last_seen]
#   field state - <on-change> [Home Assistant value]

sensor__timestamp,
  module=homeassistant,
  entity_id=<string>
    state=<text>
  <timestamp>
