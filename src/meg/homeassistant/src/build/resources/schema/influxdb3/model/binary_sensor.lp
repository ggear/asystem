################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# binary_sensor [Home Assistant binary_sensor]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     dining_air_purifier_replace_filter,
#     ipad_graham_focus,
#     iphone_graham_camera_motion,
#     iphone_graham_focus,
#     iphone_graham_kiosk_mode,
#     janes_ipad_focus,
#     janes_ipad_kiosk_mode,
#     janes_iphone_focus,
#     janes_iphone_focus_2,
#     janes_iphone_kiosk_mode,
#     kitchen_move_microphone,
#     lounge_air_purifier_replace_filter,
#     lounge_arc_microphone,
#     parents_move_microphone,
#     template_back_door_state,
#     template_bathroom_rails_plug_proxy,
#     template_ceiling_network_switch_plug_proxy,
#     template_deck_festoons_plug_proxy,
#     template_dining_air_purifier_proxy,
#     template_kitchen_coffee_machine_plug_proxy,
#     template_landing_festoons_plug_proxy,
#     template_lounge_air_purifier_proxy,
#     template_lounge_tv_plug_proxy,
#     template_rack_outlet_plug_proxy,
#     workday_sensor]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

binary_sensor,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
