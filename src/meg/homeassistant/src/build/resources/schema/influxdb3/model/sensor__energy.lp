################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor__energy [Home Assistant sensor__energy]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ceiling_network_devices_energy,
#     ceiling_network_devices_energy_daily,
#     ceiling_network_devices_energy_monthly,
#     ceiling_network_devices_energy_weekly,
#     ceiling_network_devices_energy_yearly,
#     ceiling_network_switch_plug_energy_total,
#     ceiling_network_switch_plug_energy_total_daily,
#     ceiling_network_switch_plug_energy_total_monthly,
#     ceiling_network_switch_plug_energy_total_weekly,
#     ceiling_network_switch_plug_energy_total_yearly,
#     garden_sewerage_blower_plug_energy_4,
#     home_base_energy,
#     home_base_energy_daily,
#     home_base_energy_monthly,
#     home_base_energy_weekly,
#     home_base_energy_yearly,
#     home_energy,
#     home_energy_daily,
#     home_energy_monthly,
#     home_energy_weekly,
#     home_energy_yearly,
#     lights_energy,
#     lights_energy_daily,
#     lights_energy_monthly,
#     lights_energy_weekly,
#     lights_energy_yearly,
#     lounge_tv_plug_energy_4,
#     rack_backup_plug_energy_4,
#     rack_outlet_plug_energy_total,
#     rack_outlet_plug_energy_total_daily,
#     rack_outlet_plug_energy_total_monthly,
#     rack_outlet_plug_energy_total_weekly,
#     rack_outlet_plug_energy_total_yearly,
#     server_rack_energy,
#     server_rack_energy_daily,
#     server_rack_energy_monthly,
#     server_rack_energy_weekly,
#     server_rack_energy_yearly,
#     servers_network_energy,
#     servers_network_energy_daily,
#     servers_network_energy_monthly,
#     servers_network_energy_weekly,
#     servers_network_energy_yearly]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     kWh]
#   field last_valid_state - <on-change> [Home Assistant value]
#   field next_reset - <on-change> [Home Assistant value]
#   field next_reset_str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sensor__energy,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=kWh
    last_valid_state=<float>,
    next_reset=<float>,
    value=<float>
  <timestamp>
