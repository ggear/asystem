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
#   field value - <on-change> [Home Assistant value]

sensor__wind_speed,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    value=<float>
  <timestamp>
