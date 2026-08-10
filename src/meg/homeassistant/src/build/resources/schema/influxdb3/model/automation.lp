################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# automation [Home Assistant automation]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     coffee_machine_turn_off_coffee_machine,
#     coffee_machine_turn_off_coffee_machine_fail_safe,
#     lighting_reset_adaptive_lighting_for_all_lights,
#     lighting_reset_adaptive_lighting_on_bulb_announce,
#     lighting_reset_adaptive_lighting_on_request_of_ada_lamp,
#     lighting_reset_adaptive_lighting_on_request_of_bathroom_main,
#     lighting_reset_adaptive_lighting_on_request_of_bathroom_sconces,
#     lighting_reset_adaptive_lighting_on_request_of_dining_main,
#     lighting_reset_adaptive_lighting_on_request_of_edwin_night_light,
#     lighting_reset_adaptive_lighting_on_request_of_ensuite_main,
#     lighting_reset_adaptive_lighting_on_request_of_ensuite_sconces,
#     lighting_reset_adaptive_lighting_on_request_of_graham_bedside,
#     lighting_reset_adaptive_lighting_on_request_of_hallway_main,
#     lighting_reset_adaptive_lighting_on_request_of_hallway_sconces,
#     lighting_reset_adaptive_lighting_on_request_of_jane_bedside,
#     lighting_reset_adaptive_lighting_on_request_of_kitchen_main,
#     lighting_reset_adaptive_lighting_on_request_of_laundry_main,
#     lighting_reset_adaptive_lighting_on_request_of_lounge_lamp,
#     lighting_reset_adaptive_lighting_on_request_of_lounge_main,
#     lighting_reset_adaptive_lighting_on_request_of_lounge_reading,
#     lighting_reset_adaptive_lighting_on_request_of_office_main,
#     lighting_reset_adaptive_lighting_on_request_of_pantry_main,
#     lighting_reset_adaptive_lighting_on_request_of_parents_main,
#     lighting_reset_adaptive_lighting_on_request_of_study_lamp,
#     lighting_reset_adaptive_lighting_on_request_of_tree_spotlights,
#     lighting_reset_adaptive_lighting_on_request_of_wardrobe_main,
#     routine_attempt_to_put_home_into_secure_mode_at_regular_intervals,
#     routine_back_door_state_all_off,
#     routine_back_door_state_all_on,
#     routine_back_door_state_off,
#     routine_back_door_state_on,
#     routine_front_door_state_all_off,
#     routine_front_door_state_all_on,
#     routine_front_door_state_off,
#     routine_front_door_state_on,
#     routine_put_back_door_lock_into_secure_mode,
#     routine_put_front_door_lock_into_secure_mode,
#     routine_put_home_into_movie_mode,
#     routine_put_home_into_secure_mode,
#     routine_put_home_to_sleep,
#     routine_put_home_to_sleep_via_cube,
#     routine_reset_home_to_defaults,
#     routine_run_init_code_after_startup,
#     routine_take_back_door_lock_out_of_secure_mode,
#     routine_take_front_door_lock_out_of_secure_mode,
#     routine_take_home_out_of_movie_mode,
#     routine_take_home_out_of_secure_mode,
#     routine_template_back_door_sensor_contact_last_on,
#     routine_template_front_door_sensor_contact_last_on,
#     routine_turn_early_night_lights_off,
#     routine_turn_fans_off,
#     routine_turn_night_lights_off,
#     routine_turn_night_lights_off_on_week_days,
#     routine_turn_night_lights_on,
#     routine_wake_home_up,
#     routine_wake_home_up_via_cube,
#     water_heating_turn_off_towel_rails,
#     water_heating_turn_off_towel_rails_fail_safe,
#     water_heating_turn_off_water_heater_booster,
#     water_heating_turn_off_water_heater_booster_fail_safe,
#     water_heating_turn_on_towel_rails,
#     water_heating_turn_on_water_heater_booster]
#   field last_triggered - <on-change> [Home Assistant value]
#   field last_triggered_str - <on-change> [Home Assistant value]
#   field max - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

automation,
  module=homeassistant,
  entity_id=<string>
    last_triggered=<float>,
    max=<float>,
    value=<float>
  <timestamp>
