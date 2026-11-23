################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# input_number [Home Assistant input_number]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id [Home Assistant entity_id:
#     weatherstation_console_battery_reported]
#   tag unit_of_measurement* [Home Assistant unit_of_measurement:
#     s]
#   field initial_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

input_number,
  module=homeassistant,
  entity_id=weatherstation_console_battery_reported,
  unit_of_measurement=s
    initial_str=<text>,
    value=<float>
  <timestamp>
