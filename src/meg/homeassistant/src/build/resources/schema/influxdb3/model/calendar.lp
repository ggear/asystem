################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# calendar [Home Assistant calendar]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     workday_sensor_calendar]
#   field all_day - <on-change> [Home Assistant value]
#   field description_str - <on-change> [Home Assistant value]
#   field end_time - <on-change> [Home Assistant value]
#   field end_time_str - <on-change> [Home Assistant value]
#   field location_str - <on-change> [Home Assistant value]
#   field message_str - <on-change> [Home Assistant value]
#   field start_time - <on-change> [Home Assistant value]
#   field start_time_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

calendar,
  module=homeassistant,
  entity_id=<string>
    all_day=<float>,
    end_time=<float>,
    start_time=<float>,
    value=<float>
  <timestamp>
