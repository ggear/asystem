################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__voltage [Home Assistant sensor__voltage]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bathroom_rails_plug_voltage,
#     deck_freezer_plug_voltage,
#     garden_sewerage_blower_plug_voltage,
#     kitchen_coffee_machine_plug_voltage,
#     kitchen_dish_washer_plug_voltage,
#     lounge_tv_plug_voltage,
#     rack_backup_plug_voltage,
#     server_lia_plug_voltage]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     V]
#   field value - <on-change> [Home Assistant value]

sensor__voltage,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=V
    value=<float>
  <timestamp>
