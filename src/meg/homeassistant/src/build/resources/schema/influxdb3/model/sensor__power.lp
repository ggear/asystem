################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__power [Home Assistant sensor__power]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bathroom_rails_plug_power,
#     ceiling_network_devices_power,
#     ceiling_network_switch_plug_energy_power,
#     deck_freezer_plug_power,
#     garden_sewerage_blower_plug_power,
#     home_base_power,
#     home_power,
#     lounge_tv_plug_power,
#     rack_backup_plug_power,
#     rack_outlet_plug_energy_power,
#     server_lia_plug_power,
#     server_rack_power,
#     servers_network_power]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     W]
#   field value - <on-change> [Home Assistant value]

sensor__power,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=W
    value=<float>
  <timestamp>
