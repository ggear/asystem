################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__humidity [Home Assistant sensor__humidity]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id [Home Assistant entity_id:
#     deck_festoons_plug_humidity]
#   tag unit_of_measurement* [Home Assistant unit_of_measurement:
#     %]
#   field value - <on-change> [Home Assistant value]

sensor__humidity,
  module=homeassistant,
  entity_id=deck_festoons_plug_humidity,
  unit_of_measurement=%
    value=<float>
  <timestamp>
