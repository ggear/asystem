################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sensor [Home Assistant sensor]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock_action_source_name,
#     back_door_lock_action_user,
#     bom_darlington_condition,
#     bom_darlington_extended_text_0,
#     bom_darlington_extended_text_1,
#     bom_darlington_extended_text_2,
#     bom_darlington_extended_text_3,
#     bom_darlington_fire_danger_0,
#     bom_darlington_fire_danger_1,
#     bom_darlington_fire_danger_2,
#     bom_darlington_fire_danger_3,
#     bom_darlington_icon_descriptor_0,
#     bom_darlington_icon_descriptor_1,
#     bom_darlington_icon_descriptor_2,
#     bom_darlington_icon_descriptor_3,
#     bom_darlington_icon_descriptor_4,
#     bom_darlington_icon_descriptor_5,
#     bom_darlington_icon_descriptor_6,
#     bom_darlington_icon_descriptor_7,
#     bom_darlington_later_label,
#     bom_darlington_mdi_icon_0,
#     bom_darlington_mdi_icon_1,
#     bom_darlington_mdi_icon_2,
#     bom_darlington_mdi_icon_3,
#     bom_darlington_mdi_icon_4,
#     bom_darlington_mdi_icon_5,
#     bom_darlington_mdi_icon_6,
#     bom_darlington_mdi_icon_7,
#     bom_darlington_now_label,
#     bom_darlington_rain_amount_range_0,
#     bom_darlington_rain_amount_range_1,
#     bom_darlington_rain_amount_range_2,
#     bom_darlington_rain_amount_range_3,
#     bom_darlington_rain_amount_range_4,
#     bom_darlington_rain_amount_range_5,
#     bom_darlington_rain_amount_range_6,
#     bom_darlington_rain_amount_range_7,
#     bom_darlington_rain_chance_0,
#     bom_darlington_rain_chance_1,
#     bom_darlington_rain_chance_2,
#     bom_darlington_rain_chance_3,
#     bom_darlington_rain_chance_4,
#     bom_darlington_rain_chance_5,
#     bom_darlington_rain_chance_6,
#     bom_darlington_rain_chance_7,
#     bom_darlington_short_text_0,
#     bom_darlington_short_text_1,
#     bom_darlington_short_text_2,
#     bom_darlington_short_text_3,
#     bom_darlington_short_text_4,
#     bom_darlington_short_text_5,
#     bom_darlington_short_text_6,
#     bom_darlington_short_text_7,
#     bom_darlington_uv_category_0,
#     bom_darlington_uv_category_1,
#     bom_darlington_uv_category_2,
#     bom_darlington_uv_category_3,
#     bom_darlington_uv_category_4,
#     bom_darlington_uv_forecast_0,
#     bom_darlington_uv_forecast_1,
#     bom_darlington_uv_forecast_2,
#     bom_darlington_uv_forecast_3,
#     bom_darlington_uv_forecast_4,
#     bom_darlington_uv_max_index_0,
#     bom_darlington_uv_max_index_1,
#     bom_darlington_uv_max_index_2,
#     bom_darlington_uv_max_index_3,
#     bom_darlington_uv_max_index_4,
#     bom_darlington_warnings,
#     bom_darlington_wind_direction,
#     ceiling_water_booster_plug_energy_total_daily,
#     ceiling_water_booster_plug_energy_total_monthly,
#     ceiling_water_booster_plug_energy_total_weekly,
#     ceiling_water_booster_plug_energy_total_yearly,
#     deck_fans_outlet_linkquality,
#     dfes_incidents_metro_south_east_any,
#     dining_air_purifier_fan_speed,
#     dining_air_purifier_filter_age,
#     driveway_repeater_linkquality_energy_daily,
#     driveway_repeater_linkquality_energy_monthly,
#     driveway_repeater_linkquality_energy_weekly,
#     driveway_repeater_linkquality_energy_yearly,
#     front_door_lock_action_source_name,
#     garden_pool_filter_plug_energy_total_daily,
#     garden_pool_filter_plug_energy_total_monthly,
#     garden_pool_filter_plug_energy_total_weekly,
#     garden_pool_filter_plug_energy_total_yearly,
#     garden_sewerage_blower_plug_energy_daily,
#     garden_sewerage_blower_plug_energy_monthly,
#     garden_sewerage_blower_plug_energy_weekly,
#     garden_sewerage_blower_plug_energy_yearly,
#     ipad_graham_activity,
#     ipad_graham_app_version,
#     ipad_graham_audio_output,
#     ipad_graham_battery_state,
#     ipad_graham_bssid,
#     ipad_graham_connection_type,
#     ipad_graham_geocoded_location,
#     ipad_graham_last_update_trigger,
#     ipad_graham_location_permission,
#     ipad_graham_ssid,
#     ipad_graham_storage,
#     iphone_graham_activity,
#     iphone_graham_app_version,
#     iphone_graham_audio_output,
#     iphone_graham_average_active_pace,
#     iphone_graham_battery_state,
#     iphone_graham_bssid,
#     iphone_graham_connection_type,
#     iphone_graham_distance,
#     iphone_graham_floors_ascended,
#     iphone_graham_floors_descended,
#     iphone_graham_geocoded_location,
#     iphone_graham_last_update_trigger,
#     iphone_graham_location_permission,
#     iphone_graham_ssid,
#     iphone_graham_steps,
#     iphone_graham_storage,
#     iphone_graham_watch_battery_state,
#     janes_ipad_activity,
#     janes_ipad_app_version,
#     janes_ipad_audio_output,
#     janes_ipad_battery_state,
#     janes_ipad_bssid,
#     janes_ipad_connection_type,
#     janes_ipad_geocoded_location,
#     janes_ipad_last_update_trigger,
#     janes_ipad_location_permission,
#     janes_ipad_ssid,
#     janes_ipad_storage,
#     janes_iphone_activity,
#     janes_iphone_activity_2,
#     janes_iphone_app_version,
#     janes_iphone_audio_output,
#     janes_iphone_average_active_pace,
#     janes_iphone_average_active_pace_2,
#     janes_iphone_battery_state,
#     janes_iphone_battery_state_2,
#     janes_iphone_bssid,
#     janes_iphone_bssid_2,
#     janes_iphone_connection_type,
#     janes_iphone_connection_type_2,
#     janes_iphone_distance,
#     janes_iphone_distance_2,
#     janes_iphone_floors_ascended,
#     janes_iphone_floors_ascended_2,
#     janes_iphone_floors_descended,
#     janes_iphone_floors_descended_2,
#     janes_iphone_geocoded_location,
#     janes_iphone_geocoded_location_2,
#     janes_iphone_last_update_trigger,
#     janes_iphone_last_update_trigger_2,
#     janes_iphone_location_permission,
#     janes_iphone_ssid,
#     janes_iphone_ssid_2,
#     janes_iphone_steps,
#     janes_iphone_steps_2,
#     janes_iphone_storage,
#     janes_iphone_storage_2,
#     janes_iphone_watch_battery_state,
#     kitchen_fan_outlet_linkquality,
#     kitchen_fridge_plug_energy_daily,
#     kitchen_fridge_plug_energy_monthly,
#     kitchen_fridge_plug_energy_weekly,
#     kitchen_fridge_plug_energy_yearly,
#     landing_repeater_linkquality_energy_daily,
#     landing_repeater_linkquality_energy_monthly,
#     landing_repeater_linkquality_energy_weekly,
#     landing_repeater_linkquality_energy_yearly,
#     lounge_air_purifier_fan_speed,
#     lounge_air_purifier_filter_age,
#     lounge_arc_audio_input_format,
#     rack_printer_plug_energy_daily,
#     rack_printer_plug_energy_monthly,
#     rack_printer_plug_energy_weekly,
#     rack_printer_plug_energy_yearly,
#     roof_24hour_rain,
#     roof_daily_rain,
#     roof_hourly_rain,
#     roof_monthly_rain,
#     roof_rain,
#     roof_rain_rate,
#     roof_storm_rain,
#     roof_wind_direction,
#     roof_wind_gust_direction,
#     roof_wind_gust_speed,
#     roof_wind_samples,
#     roof_wind_speed,
#     roof_wind_speed_10min,
#     roof_yearly_rain,
#     server_jen_plug_energy_daily,
#     server_jen_plug_energy_monthly,
#     server_jen_plug_energy_weekly,
#     server_jen_plug_energy_yearly,
#     weatherstation_coms_signal_quality,
#     willy_wind_forecast_dominant_direction_0,
#     willy_wind_forecast_dominant_direction_1,
#     willy_wind_forecast_dominant_direction_2,
#     willy_wind_forecast_dominant_direction_3,
#     willy_wind_forecast_dominant_direction_4,
#     willy_wind_forecast_dominant_direction_5,
#     willy_wind_forecast_dominant_direction_6,
#     willy_wind_forecast_dominant_direction_abbreviation_0,
#     willy_wind_forecast_dominant_direction_abbreviation_1,
#     willy_wind_forecast_dominant_direction_abbreviation_2,
#     willy_wind_forecast_dominant_direction_abbreviation_3,
#     willy_wind_forecast_dominant_direction_abbreviation_4,
#     willy_wind_forecast_dominant_direction_abbreviation_5,
#     willy_wind_forecast_dominant_direction_abbreviation_6,
#     willy_wind_forecast_dominant_direction_text_0,
#     willy_wind_forecast_dominant_direction_text_1,
#     willy_wind_forecast_dominant_direction_text_2,
#     willy_wind_forecast_dominant_direction_text_3,
#     willy_wind_forecast_dominant_direction_text_4,
#     willy_wind_forecast_dominant_direction_text_5,
#     willy_wind_forecast_dominant_direction_text_6,
#     willy_wind_forecast_speed_max_0,
#     willy_wind_forecast_speed_max_1,
#     willy_wind_forecast_speed_max_2,
#     willy_wind_forecast_speed_max_3,
#     willy_wind_forecast_speed_max_4,
#     willy_wind_forecast_speed_max_5,
#     willy_wind_forecast_speed_max_6,
#     willy_wind_forecast_speed_min_0,
#     willy_wind_forecast_speed_min_1,
#     willy_wind_forecast_speed_min_2,
#     willy_wind_forecast_speed_min_3,
#     willy_wind_forecast_speed_min_4,
#     willy_wind_forecast_speed_min_5,
#     willy_wind_forecast_speed_min_6,
#     zigbee2mqtt_bridge_version]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     %,
#     % available,
#     Events,
#     cm,
#     floors,
#     km/h,
#     lqi,
#     m,
#     m/s,
#     minutes,
#     mm,
#     mm/h,
#     steps,
#     °]
#   field Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033) - <on-change> [Home Assistant value]
#   field Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)_str - <on-change> [Home Assistant value]
#   field Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971) - <on-change> [Home Assistant value]
#   field Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)_str - <on-change> [Home Assistant value]
#   field Administrative Area_str - <on-change> [Home Assistant value]
#   field Areas Of Interest_str - <on-change> [Home Assistant value]
#   field Available - <on-change> [Home Assistant value]
#   field Available (Important) - <on-change> [Home Assistant value]
#   field Available (Important)_str - <on-change> [Home Assistant value]
#   field Available (Opportunistic) - <on-change> [Home Assistant value]
#   field Available (Opportunistic)_str - <on-change> [Home Assistant value]
#   field Available_str - <on-change> [Home Assistant value]
#   field Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996) - <on-change> [Home Assistant value]
#   field Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)_str - <on-change> [Home Assistant value]
#   field Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037) - <on-change> [Home Assistant value]
#   field Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)_str - <on-change> [Home Assistant value]
#   field Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023) - <on-change> [Home Assistant value]
#   field Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)_str - <on-change> [Home Assistant value]
#   field Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022) - <on-change> [Home Assistant value]
#   field Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)_str - <on-change> [Home Assistant value]
#   field Cellular Technology_str - <on-change> [Home Assistant value]
#   field Confidence_str - <on-change> [Home Assistant value]
#   field Country_str - <on-change> [Home Assistant value]
#   field Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994) - <on-change> [Home Assistant value]
#   field Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)_str - <on-change> [Home Assistant value]
#   field ISO Country Code_str - <on-change> [Home Assistant value]
#   field Incident (MIDLAND, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809976)_str - <on-change> [Home Assistant value]
#   field Inland Water_str - <on-change> [Home Assistant value]
#   field Locality_str - <on-change> [Home Assistant value]
#   field Location_str - <on-change> [Home Assistant value]
#   field Low Power Mode - <on-change> [Home Assistant value]
#   field Name - <on-change> [Home Assistant value]
#   field Name_str - <on-change> [Home Assistant value]
#   field Ocean_str - <on-change> [Home Assistant value]
#   field Postal Code - <on-change> [Home Assistant value]
#   field Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011) - <on-change> [Home Assistant value]
#   field Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)_str - <on-change> [Home Assistant value]
#   field Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968) - <on-change> [Home Assistant value]
#   field Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)_str - <on-change> [Home Assistant value]
#   field Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994) - <on-change> [Home Assistant value]
#   field Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)_str - <on-change> [Home Assistant value]
#   field Sub Administrative Area_str - <on-change> [Home Assistant value]
#   field Sub Locality_str - <on-change> [Home Assistant value]
#   field Sub Thoroughfare - <on-change> [Home Assistant value]
#   field Thoroughfare_str - <on-change> [Home Assistant value]
#   field Time Zone_str - <on-change> [Home Assistant value]
#   field Total - <on-change> [Home Assistant value]
#   field Total_str - <on-change> [Home Assistant value]
#   field Types_str - <on-change> [Home Assistant value]
#   field Zones_str - <on-change> [Home Assistant value]
#   field bom_id - <on-change> [Home Assistant value]
#   field copyright_str - <on-change> [Home Assistant value]
#   field date - <on-change> [Home Assistant value]
#   field date_str - <on-change> [Home Assistant value]
#   field distance - <on-change> [Home Assistant value]
#   field forecast_region_str - <on-change> [Home Assistant value]
#   field forecast_text_str - <on-change> [Home Assistant value]
#   field forecast_type_str - <on-change> [Home Assistant value]
#   field issue_time - <on-change> [Home Assistant value]
#   field issue_time_str - <on-change> [Home Assistant value]
#   field last_valid_state_str - <on-change> [Home Assistant value]
#   field name_str - <on-change> [Home Assistant value]
#   field next_issue_time - <on-change> [Home Assistant value]
#   field next_issue_time_str - <on-change> [Home Assistant value]
#   field next_reset - <on-change> [Home Assistant value]
#   field next_reset_str - <on-change> [Home Assistant value]
#   field observation_time - <on-change> [Home Assistant value]
#   field observation_time_str - <on-change> [Home Assistant value]
#   field response_timestamp - <on-change> [Home Assistant value]
#   field response_timestamp_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field state__str - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]
#   field warnings_str - <on-change> [Home Assistant value]

sensor,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)=<float>,
    Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)=<float>,
    Available=<float>,
    Available (Important)=<float>,
    Available (Opportunistic)=<float>,
    Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)=<float>,
    Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)=<float>,
    Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)=<float>,
    Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)=<float>,
    Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)=<float>,
    Low Power Mode=<float>,
    Name=<float>,
    Postal Code=<float>,
    Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)=<float>,
    Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)=<float>,
    Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)=<float>,
    Sub Thoroughfare=<float>,
    Total=<float>,
    bom_id=<float>,
    date=<float>,
    distance=<float>,
    issue_time=<float>,
    next_issue_time=<float>,
    next_reset=<float>,
    observation_time=<float>,
    response_timestamp=<float>,
    value=<float>
  <timestamp>
