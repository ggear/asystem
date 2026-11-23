################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# device_tracker [Home Assistant device_tracker]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ipad_graham,
#     iphone_graham,
#     janes_ipad,
#     janes_iphone,
#     janes_iphone_2]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

device_tracker,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
