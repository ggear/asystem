################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__temperature [Home Assistant sensor__temperature]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan_temperature,
#     ada_temperature,
#     bom_darlington_delta_t,
#     bom_darlington_dew_point,
#     bom_darlington_max_temp,
#     bom_darlington_min_temp,
#     bom_darlington_temp,
#     bom_darlington_temp_feels_like,
#     bom_darlington_temp_later,
#     bom_darlington_temp_max_0,
#     bom_darlington_temp_max_1,
#     bom_darlington_temp_max_2,
#     bom_darlington_temp_max_3,
#     bom_darlington_temp_max_4,
#     bom_darlington_temp_max_5,
#     bom_darlington_temp_max_6,
#     bom_darlington_temp_max_7,
#     bom_darlington_temp_min_0,
#     bom_darlington_temp_min_1,
#     bom_darlington_temp_min_2,
#     bom_darlington_temp_min_3,
#     bom_darlington_temp_min_4,
#     bom_darlington_temp_min_5,
#     bom_darlington_temp_min_6,
#     bom_darlington_temp_min_7,
#     bom_darlington_temp_now,
#     compensation_sensor_ada_temperature,
#     compensation_sensor_deck_festoons_plug_temperature,
#     compensation_sensor_edwin_temperature,
#     compensation_sensor_kitchen_temperature,
#     compensation_sensor_landing_festoons_plug_temperature,
#     compensation_sensor_laundry_temperature,
#     compensation_sensor_office_basement_temperature,
#     compensation_sensor_office_dining_temperature,
#     compensation_sensor_office_lounge_temperature,
#     compensation_sensor_office_pantry_temperature,
#     compensation_sensor_office_temperature,
#     compensation_sensor_parents_temperature,
#     compensation_sensor_rack_bottom_temperature,
#     compensation_sensor_rack_top_temperature,
#     compensation_sensor_roof_temperature,
#     compensation_sensor_utility_temperature,
#     compensation_sensor_wardrobe_temperature,
#     deck_east_fan_temperature,
#     deck_festoons_plug_temperature,
#     deck_west_fan_temperature,
#     edwin_fan_temperature,
#     edwin_temperature,
#     kitchen_deck_temperature,
#     kitchen_temperature,
#     landing_festoons_plug_temperature,
#     laundry_temperature,
#     lounge_fan_temperature,
#     office_basement_temperature,
#     office_dining_temperature,
#     office_lounge_temperature,
#     office_pantry_temperature,
#     office_temperature,
#     parents_fan_temperature,
#     parents_temperature,
#     rack_bottom_temperature,
#     rack_top_temperature,
#     roof_temperature,
#     template_deck_festoons_plug_temperature_proxy,
#     template_utility_temperature_proxy,
#     template_wardrobe_temperature_proxy,
#     utility_temperature,
#     wardrobe_temperature]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     °C]
#   field bom_id - <on-change> [Home Assistant value]
#   field copyright_str - <on-change> [Home Assistant value]
#   field date - <on-change> [Home Assistant value]
#   field date_str - <on-change> [Home Assistant value]
#   field distance - <on-change> [Home Assistant value]
#   field forecast_region_str - <on-change> [Home Assistant value]
#   field forecast_type_str - <on-change> [Home Assistant value]
#   field issue_time - <on-change> [Home Assistant value]
#   field issue_time_str - <on-change> [Home Assistant value]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field name_str - <on-change> [Home Assistant value]
#   field next_issue_time - <on-change> [Home Assistant value]
#   field next_issue_time_str - <on-change> [Home Assistant value]
#   field observation_time - <on-change> [Home Assistant value]
#   field observation_time_str - <on-change> [Home Assistant value]
#   field response_timestamp - <on-change> [Home Assistant value]
#   field response_timestamp_str - <on-change> [Home Assistant value]
#   field time_observed - <on-change> [Home Assistant value]
#   field time_observed_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__temperature,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    bom_id=<float>,
    date=<float>,
    distance=<float>,
    issue_time=<float>,
    latitude=<float>,
    longitude=<float>,
    next_issue_time=<float>,
    observation_time=<float>,
    response_timestamp=<float>,
    time_observed=<float>,
    value=<float>
  <timestamp>
