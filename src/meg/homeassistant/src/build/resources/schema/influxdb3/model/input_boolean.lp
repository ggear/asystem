################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# input_boolean [Home Assistant input_boolean]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     home_started]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

input_boolean,
  module=homeassistant,
  entity_id=home_started
    state=<text>,
    value=<float>
  <timestamp>
