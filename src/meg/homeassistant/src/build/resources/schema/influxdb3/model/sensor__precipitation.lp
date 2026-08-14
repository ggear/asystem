################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__precipitation [Home Assistant sensor__precipitation]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bom_darlington_rain_amount_max_0,
#     bom_darlington_rain_amount_max_1,
#     bom_darlington_rain_amount_max_2,
#     bom_darlington_rain_amount_max_3,
#     bom_darlington_rain_amount_max_4,
#     bom_darlington_rain_amount_max_5,
#     bom_darlington_rain_amount_max_6,
#     bom_darlington_rain_amount_max_7,
#     bom_darlington_rain_amount_min_0,
#     bom_darlington_rain_amount_min_1,
#     bom_darlington_rain_amount_min_2,
#     bom_darlington_rain_amount_min_3,
#     bom_darlington_rain_amount_min_4,
#     bom_darlington_rain_amount_min_5,
#     bom_darlington_rain_amount_min_6,
#     bom_darlington_rain_amount_min_7]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     mm]
#   field value - <on-change> [Home Assistant value]

sensor__precipitation,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=mm
    value=<float>
  <timestamp>
