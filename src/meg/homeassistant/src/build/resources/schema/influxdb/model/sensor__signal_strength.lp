################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__signal_strength [Home Assistant sensor__signal_strength]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id [Home Assistant entity_id:
#     template_weatherstation_coms_signal_quality_percentage]
#   tag unit_of_measurement* [Home Assistant unit_of_measurement:
#     %]
#   field value - <on-change> [Home Assistant value]

sensor__signal_strength,
  module=homeassistant,
  entity_id=template_weatherstation_coms_signal_quality_percentage,
  unit_of_measurement=%
    value=<float>
  <timestamp>
