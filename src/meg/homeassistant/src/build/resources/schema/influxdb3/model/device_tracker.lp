################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# device_tracker [Home Assistant device_tracker]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ipad_graham,
#     iphone_graham,
#     janes_ipad,
#     janes_iphone,
#     janes_iphone_2]
#   field altitude - <on-change> [Home Assistant value]
#   field battery_level - <on-change> [Home Assistant value]
#   field gps_accuracy - <on-change> [Home Assistant value]
#   field in_zones_str - <on-change> [Home Assistant value]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field source_type_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field tracking_type_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]
#   field vertical_accuracy - <on-change> [Home Assistant value]

device_tracker,
  module=homeassistant,
  entity_id=<string>
    altitude=<float>,
    battery_level=<float>,
    gps_accuracy=<float>,
    latitude=<float>,
    longitude=<float>,
    value=<float>,
    vertical_accuracy=<float>
  <timestamp>
