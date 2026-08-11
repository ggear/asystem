################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor__safety [Home Assistant binary_sensor__safety]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     bom_darlington_bushwalkers_alert,
#     bom_darlington_fire_weather_warning,
#     bom_darlington_flood_warning,
#     bom_darlington_flood_watch,
#     bom_darlington_frost_warning,
#     bom_darlington_hazardous_surf_warning,
#     bom_darlington_heatwave_warning,
#     bom_darlington_marine_wind_warning,
#     bom_darlington_severe_thunderstorm_warning,
#     bom_darlington_severe_weather_warning,
#     bom_darlington_sheep_graziers_warning,
#     bom_darlington_tropical_cyclone_warning]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor__safety,
  module=homeassistant,
  entity_id=<bom_darlington_bushwalkers_alert|bom_darlington_fire_weather_warning|bom_darlington_flood_warning|bom_darlington_flood_watch|bom_darlington_frost_warning|bom_darlington_hazardous_surf_warning|bom_darlington_heatwave_warning|bom_darlington_marine_wind_warning|bom_darlington_severe_thunderstorm_warning|bom_darlington_severe_weather_warning|bom_darlington_sheep_graziers_warning|bom_darlington_tropical_cyclone_warning>
    value=<float>
  <timestamp>
