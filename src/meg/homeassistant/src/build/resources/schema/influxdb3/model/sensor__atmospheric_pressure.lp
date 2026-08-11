################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__atmospheric_pressure [Home Assistant sensor__atmospheric_pressure]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_atmospheric_pressure,
#     edwin_atmospheric_pressure,
#     kitchen_atmospheric_pressure,
#     laundry_atmospheric_pressure,
#     office_atmospheric_pressure,
#     parents_atmospheric_pressure]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     hPa]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__atmospheric_pressure,
  module=homeassistant,
  entity_id=<ada_atmospheric_pressure|edwin_atmospheric_pressure|kitchen_atmospheric_pressure|laundry_atmospheric_pressure|office_atmospheric_pressure|parents_atmospheric_pressure>,
  unit_of_measurement=hPa
    latitude=<float>,
    longitude=<float>,
    value=<float>
  <timestamp>
