################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# media_player [Home Assistant media_player]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     ada_tablet,
#     ada_tablet_2,
#     kitchen_home,
#     lounge_tv,
#     nesthubfb4d,
#     pixel_tablet,
#     pixel_tablet_2]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

media_player,
  module=homeassistant,
  entity_id=<string>
    state=<text>,
    value=<float>
  <timestamp>
