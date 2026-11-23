################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# media_player__tv [Home Assistant media_player__tv]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     lg_webos_smart_tv]
#   field sound_output_str - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

media_player__tv,
  module=homeassistant,
  entity_id=lg_webos_smart_tv
    sound_output_str=<text>,
    state=<text>,
    value=<float>
  <timestamp>
