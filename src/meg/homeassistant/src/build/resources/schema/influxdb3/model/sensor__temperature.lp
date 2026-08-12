################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__temperature [Home Assistant sensor__temperature]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     compensation_sensor_landing_festoons_plug_temperature,
#     landing_festoons_plug_temperature]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     °C]
#   field value - <on-change> [Home Assistant value]

sensor__temperature,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=°C
    value=<float>
  <timestamp>
