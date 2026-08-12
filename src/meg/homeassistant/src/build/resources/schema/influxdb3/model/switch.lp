################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# switch [Home Assistant switch]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     adaptive_lighting_ambient,
#     adaptive_lighting_ambient_dimming,
#     adaptive_lighting_ambient_narrowband_dimming,
#     adaptive_lighting_night,
#     adaptive_lighting_task,
#     adaptive_lighting_task_narrowband,
#     service_influxdb3]
#   field assumed_state - <on-change> [Home Assistant value]
#   field autoreset_time_remaining_str - <on-change> [Home Assistant value]
#   field brightness_pct - <on-change> [Home Assistant value]
#   field configuration_str - <on-change> [Home Assistant value]
#   field force_rgb_color - <on-change> [Home Assistant value]
#   field rgb_color - <on-change> [Home Assistant value]
#   field rgb_color_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field sun_position - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

switch,
  module=homeassistant,
  entity_id=<string>
    assumed_state=<float>,
    brightness_pct=<float>,
    force_rgb_color=<float>,
    rgb_color=<float>,
    sun_position=<float>,
    value=<float>
  <timestamp>
