################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# media_player__speaker [Home Assistant media_player__speaker]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_home,
#     edwin_home,
#     lounge_home]
#   field media_content_type_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]
#   field volume_level - <on-change> [Home Assistant value]

media_player__speaker,
  module=homeassistant,
  entity_id=<string>
    media_content_type_str=<text>,
    state=<text>,
    value=<float>,
    volume_level=<float>
  <timestamp>
