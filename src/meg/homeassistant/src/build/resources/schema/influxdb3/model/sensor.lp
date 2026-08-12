################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor [Home Assistant sensor]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id [Home Assistant entity_id:
#     deck_fans_outlet_linkquality]
#   tag unit_of_measurement* [Home Assistant unit_of_measurement:
#     lqi]
#   field value - <on-change> [Home Assistant value]

sensor,
  module=homeassistant,
  entity_id=deck_fans_outlet_linkquality,
  unit_of_measurement=lqi
    value=<float>
  <timestamp>
