################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__humidity [Home Assistant sensor__humidity]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_humidity,
#     bom_darlington_humidity,
#     edwin_humidity,
#     kitchen_deck_humidity,
#     kitchen_humidity,
#     laundry_humidity,
#     office_basement_humidity,
#     office_dining_humidity,
#     office_humidity,
#     office_lounge_humidity,
#     office_pantry_humidity,
#     parents_humidity,
#     roof_humidity,
#     wardrobe_humidity]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     %]
#   field value - <on-change> [Home Assistant value]

sensor__humidity,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=%
    value=<float>
  <timestamp>
