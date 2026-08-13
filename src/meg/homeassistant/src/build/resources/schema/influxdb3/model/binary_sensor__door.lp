################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__door [Home Assistant binary_sensor__door]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_sensor_contact]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__door,
  module=homeassistant,
  entity_id=back_door_sensor_contact
    state=<text>,
    value=<float>
  <timestamp>
