################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# input_boolean [Home Assistant input_boolean]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock_security,
#     home_security,
#     home_security_triggered,
#     home_sleep,
#     home_started]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

input_boolean,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
