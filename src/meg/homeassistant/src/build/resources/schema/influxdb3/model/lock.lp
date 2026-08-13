################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# lock [Home Assistant lock]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock,
#     front_door_lock]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

lock,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
