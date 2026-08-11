################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# input_boolean [Home Assistant input_boolean]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     back_door_lock_security,
#     front_door_lock_security,
#     home_security,
#     home_security_triggered,
#     home_sleep,
#     home_started,
#     lighting_reset_adaptive_lighting_ada_lamp,
#     lighting_reset_adaptive_lighting_bathroom_main,
#     lighting_reset_adaptive_lighting_dining_main,
#     lighting_reset_adaptive_lighting_ensuite_main,
#     lighting_reset_adaptive_lighting_ensuite_sconces,
#     lighting_reset_adaptive_lighting_kitchen_main,
#     lighting_reset_adaptive_lighting_laundry_main,
#     lighting_reset_adaptive_lighting_lounge_lamp,
#     lighting_reset_adaptive_lighting_office_main,
#     lighting_reset_adaptive_lighting_pantry_main,
#     lighting_reset_adaptive_lighting_parents_main,
#     lighting_reset_adaptive_lighting_wardrobe_main]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

input_boolean,
  module=homeassistant,
  entity_id=<back_door_lock_security|front_door_lock_security|home_security|home_security_triggered|home_sleep|home_started|lighting_reset_adaptive_lighting_ada_lamp|lighting_reset_adaptive_lighting_bathroom_main|lighting_reset_adaptive_lighting_dining_main|lighting_reset_adaptive_lighting_ensuite_main|lighting_reset_adaptive_lighting_ensuite_sconces|lighting_reset_adaptive_lighting_kitchen_main|lighting_reset_adaptive_lighting_laundry_main|lighting_reset_adaptive_lighting_lounge_lamp|lighting_reset_adaptive_lighting_office_main|lighting_reset_adaptive_lighting_pantry_main|lighting_reset_adaptive_lighting_parents_main|lighting_reset_adaptive_lighting_wardrobe_main>
    value=<float>
  <timestamp>
