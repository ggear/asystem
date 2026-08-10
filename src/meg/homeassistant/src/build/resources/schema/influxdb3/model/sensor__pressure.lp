################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__pressure [Home Assistant sensor__pressure]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     iphone_graham_pressure,
#     janes_ipad_pressure,
#     janes_iphone_pressure,
#     roof_barometer_pressure]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     hPa,
#     mbar]
#   field value - <on-change> [Home Assistant value]

sensor__pressure,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    value=<float>
  <timestamp>
