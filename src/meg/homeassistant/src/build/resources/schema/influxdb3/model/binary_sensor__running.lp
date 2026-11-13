################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__running [Home Assistant binary_sensor__running]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     rackmains_ups_calibrating]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__running,
  module=homeassistant,
  entity_id=rackmains_ups_calibrating
    state=<text>,
    value=<float>
  <timestamp>
