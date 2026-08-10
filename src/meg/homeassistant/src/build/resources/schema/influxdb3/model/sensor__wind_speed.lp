################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__wind_speed [Home Assistant sensor__wind_speed]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bom_darlington_gust_speed_kilometre,
#     bom_darlington_gust_speed_knot,
#     bom_darlington_wind_speed_kilometre,
#     bom_darlington_wind_speed_knot]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     km/h,
#     kn]
#   field bom_id - <on-change> [Home Assistant value]
#   field copyright_str - <on-change> [Home Assistant value]
#   field distance - <on-change> [Home Assistant value]
#   field issue_time - <on-change> [Home Assistant value]
#   field issue_time_str - <on-change> [Home Assistant value]
#   field name_str - <on-change> [Home Assistant value]
#   field observation_time - <on-change> [Home Assistant value]
#   field observation_time_str - <on-change> [Home Assistant value]
#   field response_timestamp - <on-change> [Home Assistant value]
#   field response_timestamp_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__wind_speed,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    bom_id=<float>,
    distance=<float>,
    issue_time=<float>,
    observation_time=<float>,
    response_timestamp=<float>,
    value=<float>
  <timestamp>
