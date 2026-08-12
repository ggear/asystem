################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# media_player__speaker [Home Assistant media_player__speaker]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_home,
#     edwin_home,
#     kitchen_five,
#     kitchen_move,
#     lounge_arc,
#     lounge_home,
#     parents_move]
#   field media_content_type_str - <on-change> [Home Assistant value]
#   field media_duration - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]
#   field volume_level - <on-change> [Home Assistant value]

media_player__speaker,
  module=homeassistant,
  entity_id=<string>
    media_content_type_str=<text>,
    media_duration=<float>,
    state=<text>,
    value=<float>,
    volume_level=<float>
  <timestamp>
