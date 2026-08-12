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
#   field value - <on-change> [Home Assistant value]

sensor__atmospheric_pressure,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=hPa
    value=<float>
  <timestamp>
