################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__humidity [Home Assistant sensor__humidity]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_humidity,
#     bom_darlington_humidity,
#     deck_festoons_plug_humidity,
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
#   field bom_id - <on-change> [Home Assistant value]
#   field copyright_str - <on-change> [Home Assistant value]
#   field distance - <on-change> [Home Assistant value]
#   field issue_time - <on-change> [Home Assistant value]
#   field issue_time_str - <on-change> [Home Assistant value]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field name_str - <on-change> [Home Assistant value]
#   field observation_time - <on-change> [Home Assistant value]
#   field observation_time_str - <on-change> [Home Assistant value]
#   field response_timestamp - <on-change> [Home Assistant value]
#   field response_timestamp_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__humidity,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=%
    bom_id=<float>,
    distance=<float>,
    issue_time=<float>,
    latitude=<float>,
    longitude=<float>,
    observation_time=<float>,
    response_timestamp=<float>,
    value=<float>
  <timestamp>
