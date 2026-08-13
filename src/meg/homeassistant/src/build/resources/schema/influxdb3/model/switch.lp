################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# switch [Home Assistant switch]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_desk_outlet,
#     bathroom_rails_plug,
#     bathroom_rails_plug_none,
#     ceiling_network_switch_plug,
#     deck_fans_outlet,
#     deck_freezer_plug,
#     deck_freezer_plug_none,
#     garden_sewerage_blower_plug,
#     garden_sewerage_blower_plug_none,
#     kitchen_coffee_machine_plug,
#     kitchen_coffee_machine_plug_none,
#     kitchen_dish_washer_plug,
#     kitchen_dish_washer_plug_none,
#     kitchen_fan_outlet,
#     kitchen_fridge_plug,
#     lounge_tv_plug,
#     lounge_tv_plug_none,
#     network_certificate,
#     network_domain,
#     network_ethernet,
#     network_internet,
#     network_weewx,
#     network_wireless,
#     network_zigbee,
#     rack_backup_plug,
#     rack_backup_plug_none,
#     rack_fans_plug,
#     rack_outlet_plug,
#     rack_screen_plug,
#     server_jen_plug,
#     server_lia_plug_none,
#     service_grafana,
#     service_homeassistant,
#     service_influxdb3,
#     service_letsencrypt,
#     service_mariadb,
#     service_mlflow,
#     service_mlserver,
#     service_network,
#     service_nginx,
#     service_openra,
#     service_plex,
#     service_postgres,
#     service_sabnzbd,
#     service_sonarr,
#     service_tempstat,
#     service_vernemq,
#     service_weewx,
#     service_wrangle,
#     service_zigbee2mqtt,
#     zigbee2mqtt_bridge_permit_join]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

switch,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
