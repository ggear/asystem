################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# person [Home Assistant person]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     graham_gear,
#     jane_thomson]
#   field gps_accuracy - <on-change> [Home Assistant value]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

person,
  module=homeassistant,
  entity_id=<string>
    gps_accuracy=<float>,
    latitude=<float>,
    longitude=<float>,
    state=<text>,
    value=<float>
  <timestamp>
