################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__sound_pressure [Home Assistant sensor__sound_pressure]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_noise,
#     edwin_noise,
#     kitchen_noise,
#     laundry_noise,
#     office_noise,
#     parents_noise]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     dB]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__sound_pressure,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=dB
    latitude=<float>,
    longitude=<float>,
    value=<float>
  <timestamp>
