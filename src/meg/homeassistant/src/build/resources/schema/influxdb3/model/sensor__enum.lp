################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__enum [Home Assistant sensor__enum]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_health_index,
#     backup_backup_manager_state,
#     edwin_health_index,
#     laundry_health_index,
#     parents_health_index,
#     pixel_tablet_battery_state,
#     pixel_tablet_battery_state_2,
#     pixel_tablet_charger_type,
#     pixel_tablet_charger_type_2,
#     tablet_ada_battery_state,
#     tablet_ada_battery_state_2,
#     tablet_ada_charger_type,
#     tablet_ada_charger_type_2,
#     tablet_edwin_battery_state_2,
#     tablet_edwin_charger_type_2]
#   field latitude - <on-change> [Home Assistant value]
#   field longitude - <on-change> [Home Assistant value]
#   field options_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]

sensor__enum,
  module=homeassistant,
  entity_id=<ada_health_index|backup_backup_manager_state|edwin_health_index|laundry_health_index|parents_health_index|pixel_tablet_battery_state|pixel_tablet_battery_state_2|pixel_tablet_charger_type|pixel_tablet_charger_type_2|tablet_ada_battery_state|tablet_ada_battery_state_2|tablet_ada_charger_type|tablet_ada_charger_type_2|tablet_edwin_battery_state_2|tablet_edwin_charger_type_2>
    latitude=<float>,
    longitude=<float>
  <timestamp>
