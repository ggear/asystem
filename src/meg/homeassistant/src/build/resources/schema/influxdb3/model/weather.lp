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
#   field fire_danger_str - <on-change> [Home Assistant value]
#   field humidity - <on-change> [Home Assistant value]
#   field later_label_str - <on-change> [Home Assistant value]
#   field later_temp - <on-change> [Home Assistant value]
#   field now_label_str - <on-change> [Home Assistant value]
#   field now_temp - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field sunrise - <on-change> [Home Assistant value]
#   field sunrise_str - <on-change> [Home Assistant value]
#   field sunset - <on-change> [Home Assistant value]
#   field sunset_str - <on-change> [Home Assistant value]
#   field temperature - <on-change> [Home Assistant value]
#   field uv_category_str - <on-change> [Home Assistant value]
#   field uv_end_time - <on-change> [Home Assistant value]
#   field uv_end_time_str - <on-change> [Home Assistant value]
#   field uv_index - <on-change> [Home Assistant value]
#   field uv_start_time - <on-change> [Home Assistant value]
#   field uv_start_time_str - <on-change> [Home Assistant value]
#   field warning_count - <on-change> [Home Assistant value]
#   field wind_bearing_str - <on-change> [Home Assistant value]
#   field wind_gust_speed - <on-change> [Home Assistant value]
#   field wind_speed - <on-change> [Home Assistant value]

weather,
  module=homeassistant,
  entity_id=bom_darlington
    apparent_temperature=<float>,
    dew_point=<float>,
    fire_danger_str=<text>,
    humidity=<float>,
    later_label_str=<text>,
    later_temp=<float>,
    now_label_str=<text>,
    now_temp=<float>,
    state=<text>,
    sunrise=<float>,
    sunrise_str=<text>,
    sunset=<float>,
    sunset_str=<text>,
    temperature=<float>,
    uv_category_str=<text>,
    uv_end_time=<float>,
    uv_end_time_str=<text>,
    uv_index=<float>,
    uv_start_time=<float>,
    uv_start_time_str=<text>,
    warning_count=<float>,
    wind_bearing_str=<text>,
    wind_gust_speed=<float>,
    wind_speed=<float>
  <timestamp>
