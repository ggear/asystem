################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# weather [Home Assistant weather]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bom_darlington]
#   field apparent_temperature - <on-change> [Home Assistant value]
#   field dew_point - <on-change> [Home Assistant value]
#   field extended_text_str - <on-change> [Home Assistant value]
#   field fire_danger_str - <on-change> [Home Assistant value]
#   field humidity - <on-change> [Home Assistant value]
#   field later_label_str - <on-change> [Home Assistant value]
#   field later_temp - <on-change> [Home Assistant value]
#   field now_label_str - <on-change> [Home Assistant value]
#   field now_temp - <on-change> [Home Assistant value]
#   field precipitation_unit_str - <on-change> [Home Assistant value]
#   field pressure_unit_str - <on-change> [Home Assistant value]
#   field short_text_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field station_id - <on-change> [Home Assistant value]
#   field station_name_str - <on-change> [Home Assistant value]
#   field sunrise - <on-change> [Home Assistant value]
#   field sunrise_str - <on-change> [Home Assistant value]
#   field sunset - <on-change> [Home Assistant value]
#   field sunset_str - <on-change> [Home Assistant value]
#   field temperature - <on-change> [Home Assistant value]
#   field temperature_unit_str - <on-change> [Home Assistant value]
#   field uv_category_str - <on-change> [Home Assistant value]
#   field uv_end_time - <on-change> [Home Assistant value]
#   field uv_end_time_str - <on-change> [Home Assistant value]
#   field uv_index - <on-change> [Home Assistant value]
#   field uv_start_time - <on-change> [Home Assistant value]
#   field uv_start_time_str - <on-change> [Home Assistant value]
#   field visibility_unit_str - <on-change> [Home Assistant value]
#   field warning_count - <on-change> [Home Assistant value]
#   field wind_bearing_str - <on-change> [Home Assistant value]
#   field wind_gust_speed - <on-change> [Home Assistant value]
#   field wind_speed - <on-change> [Home Assistant value]
#   field wind_speed_unit_str - <on-change> [Home Assistant value]

weather,
  module=homeassistant,
  entity_id=bom_darlington
    apparent_temperature=<float>,
    dew_point=<float>,
    humidity=<float>,
    later_temp=<float>,
    now_temp=<float>,
    station_id=<float>,
    sunrise=<float>,
    sunset=<float>,
    temperature=<float>,
    uv_end_time=<float>,
    uv_index=<float>,
    uv_start_time=<float>,
    warning_count=<float>,
    wind_gust_speed=<float>,
    wind_speed=<float>
  <timestamp>
