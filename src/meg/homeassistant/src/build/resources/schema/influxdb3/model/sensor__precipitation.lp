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
#   field value - <on-change> [Home Assistant value]

sensor__precipitation,
  module=homeassistant,
  entity_id=<bom_darlington_rain_amount_max_0|bom_darlington_rain_amount_max_1|bom_darlington_rain_amount_max_2|bom_darlington_rain_amount_max_3|bom_darlington_rain_amount_max_4|bom_darlington_rain_amount_max_5|bom_darlington_rain_amount_max_6|bom_darlington_rain_amount_max_7|bom_darlington_rain_amount_min_0|bom_darlington_rain_amount_min_1|bom_darlington_rain_amount_min_2|bom_darlington_rain_amount_min_3|bom_darlington_rain_amount_min_4|bom_darlington_rain_amount_min_5|bom_darlington_rain_amount_min_6|bom_darlington_rain_amount_min_7>,
  unit_of_measurement=mm
    date=<float>,
    issue_time=<float>,
    next_issue_time=<float>,
    response_timestamp=<float>,
    value=<float>
  <timestamp>
