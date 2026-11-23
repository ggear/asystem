################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__frequency [Home Assistant sensor__frequency]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id [Home Assistant entity_id:
#     rackmains_output_hertz]
#   tag unit_of_measurement* [Home Assistant unit_of_measurement:
#     Hz]
#   field value - <on-change> [Home Assistant value]

sensor__frequency,
  module=homeassistant,
  entity_id=rackmains_output_hertz,
  unit_of_measurement=Hz
    value=<float>
  <timestamp>
