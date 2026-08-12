################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__connectivity [Home Assistant binary_sensor__connectivity]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_connectivity,
#     bathroom_rails_plug_connectivity,
#     deck_freezer_plug_connectivity,
#     edwin_connectivity,
#     garden_sewerage_blower_plug_connectivity,
#     ignore_connectivity,
#     ignore_connectivity_2,
#     ignore_connectivity_3,
#     kitchen_coffee_machine_plug_connectivity,
#     kitchen_connectivity,
#     kitchen_deck_connectivity,
#     kitchen_dish_washer_plug_connectivity,
#     laundry_connectivity,
#     lounge_tv_plug_connectivity,
#     office_basement_connectivity,
#     office_connectivity,
#     office_dining_connectivity,
#     office_lounge_connectivity,
#     office_pantry_connectivity,
#     parents_connectivity,
#     rack_backup_plug_connectivity,
#     server_lia_plug_connectivity,
#     zigbee2mqtt_bridge_connection_state]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__connectivity,
  module=homeassistant,
  entity_id=<string>
    latitude=<float>,
    longitude=<float>,
    value=<float>
  <timestamp>
