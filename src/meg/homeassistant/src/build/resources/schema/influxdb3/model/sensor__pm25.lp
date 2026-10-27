################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__pm25 [Home Assistant sensor__pm25]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     template_dining_air_purifier_pm25,
#     template_kitchen_air_purifier_pm25,
#     template_lounge_air_purifier_pm25,
#     template_parents_air_purifier_pm25]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     µg/m³]
#   field value - <on-change> [Home Assistant value]

sensor__pm25,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=µg/m³
    value=<float>
  <timestamp>
