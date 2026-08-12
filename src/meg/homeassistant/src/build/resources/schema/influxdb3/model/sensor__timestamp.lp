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
#     bom_darlington_uv_end_time_4,
#     bom_darlington_uv_start_time_0,
#     bom_darlington_uv_start_time_1,
#     bom_darlington_uv_start_time_2,
#     bom_darlington_uv_start_time_3,
#     bom_darlington_uv_start_time_4,
#     deck_fans_outlet_last_seen,
#     kitchen_fan_outlet_last_seen,
#     sun_next_dawn,
#     sun_next_dusk,
#     sun_next_midnight,
#     sun_next_noon,
#     sun_next_rising,
#     sun_next_setting]
#   field copyright_str - <on-change> [Home Assistant value]
#   field date - <on-change> [Home Assistant value]
#   field date_str - <on-change> [Home Assistant value]
#   field forecast_region_str - <on-change> [Home Assistant value]
#   field forecast_type_str - <on-change> [Home Assistant value]
#   field issue_time - <on-change> [Home Assistant value]
#   field issue_time_str - <on-change> [Home Assistant value]
#   field next_issue_time - <on-change> [Home Assistant value]
#   field next_issue_time_str - <on-change> [Home Assistant value]
#   field response_timestamp - <on-change> [Home Assistant value]
#   field response_timestamp_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]

sensor__timestamp,
  module=homeassistant,
  entity_id=<string>
    date=<float>,
    issue_time=<float>,
    next_issue_time=<float>,
    response_timestamp=<float>
  <timestamp>
