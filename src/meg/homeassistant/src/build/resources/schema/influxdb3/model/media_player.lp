################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# media_player [Home Assistant media_player]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     kitchen_home,
#     nesthubfb4d,
#     pixel_tablet]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

media_player,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
