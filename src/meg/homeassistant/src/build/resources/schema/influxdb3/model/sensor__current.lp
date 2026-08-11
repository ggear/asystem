################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__current [Home Assistant sensor__current]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bathroom_rails_plug_current,
#     deck_freezer_plug_current,
#     garden_sewerage_blower_plug_current,
#     kitchen_coffee_machine_plug_current,
#     kitchen_dish_washer_plug_current,
#     lounge_tv_plug_current,
#     rack_backup_plug_current,
#     server_lia_plug_current]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     A]
#   field value - <on-change> [Home Assistant value]

sensor__current,
  module=homeassistant,
  entity_id=<bathroom_rails_plug_current|deck_freezer_plug_current|garden_sewerage_blower_plug_current|kitchen_coffee_machine_plug_current|kitchen_dish_washer_plug_current|lounge_tv_plug_current|rack_backup_plug_current|server_lia_plug_current>,
  unit_of_measurement=A
    value=<float>
  <timestamp>
