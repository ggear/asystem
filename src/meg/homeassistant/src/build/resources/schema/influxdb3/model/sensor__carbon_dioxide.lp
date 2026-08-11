################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__carbon_dioxide [Home Assistant sensor__carbon_dioxide]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_carbon_dioxide,
#     edwin_carbon_dioxide,
#     kitchen_carbon_dioxide,
#     laundry_carbon_dioxide,
#     office_carbon_dioxide,
#     office_dining_carbon_dioxide,
#     office_lounge_carbon_dioxide,
#     office_pantry_carbon_dioxide,
#     parents_carbon_dioxide]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     ppm]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__carbon_dioxide,
  module=homeassistant,
  entity_id=<ada_carbon_dioxide|edwin_carbon_dioxide|kitchen_carbon_dioxide|laundry_carbon_dioxide|office_carbon_dioxide|office_dining_carbon_dioxide|office_lounge_carbon_dioxide|office_pantry_carbon_dioxide|parents_carbon_dioxide>,
  unit_of_measurement=ppm
    latitude=<float>,
    longitude=<float>,
    value=<float>
  <timestamp>
