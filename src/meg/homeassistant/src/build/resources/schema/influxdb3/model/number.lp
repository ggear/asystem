################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# number [Home Assistant number]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_fan_auto_comfort_heat_assist_speed,
#     ada_fan_auto_comfort_maximum_speed,
#     ada_fan_auto_comfort_minimum_speed,
#     ada_fan_light_motion_sense_timeout,
#     ada_fan_light_return_to_auto_timeout,
#     ada_fan_motion_sense_timeout,
#     ada_fan_return_to_auto_timeout,
#     deck_east_fan_auto_comfort_heat_assist_speed,
#     deck_east_fan_auto_comfort_maximum_speed,
#     deck_east_fan_auto_comfort_minimum_speed,
#     deck_east_fan_motion_sense_timeout,
#     deck_east_fan_return_to_auto_timeout,
#     deck_west_fan_auto_comfort_heat_assist_speed,
#     deck_west_fan_auto_comfort_maximum_speed,
#     deck_west_fan_auto_comfort_minimum_speed,
#     deck_west_fan_motion_sense_timeout,
#     deck_west_fan_return_to_auto_timeout,
#     edwin_fan_auto_comfort_heat_assist_speed,
#     edwin_fan_auto_comfort_maximum_speed,
#     edwin_fan_auto_comfort_minimum_speed,
#     edwin_fan_light_motion_sense_timeout,
#     edwin_fan_light_return_to_auto_timeout,
#     edwin_fan_motion_sense_timeout,
#     edwin_fan_return_to_auto_timeout,
#     kitchen_five_balance,
#     kitchen_move_balance,
#     lounge_arc_audio_delay,
#     lounge_arc_balance,
#     lounge_arc_music_surround_level,
#     lounge_arc_sub_gain,
#     lounge_arc_surround_level,
#     lounge_fan_auto_comfort_heat_assist_speed,
#     lounge_fan_auto_comfort_maximum_speed,
#     lounge_fan_auto_comfort_minimum_speed,
#     lounge_fan_light_motion_sense_timeout,
#     lounge_fan_light_return_to_auto_timeout,
#     lounge_fan_motion_sense_timeout,
#     lounge_fan_return_to_auto_timeout,
#     parents_fan_auto_comfort_heat_assist_speed,
#     parents_fan_auto_comfort_maximum_speed,
#     parents_fan_auto_comfort_minimum_speed,
#     parents_fan_motion_sense_timeout,
#     parents_fan_return_to_auto_timeout,
#     parents_move_balance]
#   tag unit_of_measurement [Home Assistant unit_of_measurement:
#     s]
#   field max - <on-change> [Home Assistant value]
#   field min - <on-change> [Home Assistant value]
#   field step - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

number,
  module=homeassistant,
  entity_id=<string>,
  unit_of_measurement=<string>
    max=<float>,
    min=<float>,
    step=<float>,
    value=<float>
  <timestamp>
