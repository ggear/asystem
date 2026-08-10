################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# sun [Home Assistant sun]
#   cadence <on-change>
#   tag module [always 'homeassistant']
#   tag entity_id* [Home Assistant entity_id:
#     sun]
#   field azimuth - <on-change> [Home Assistant value]
#   field elevation - <on-change> [Home Assistant value]
#   field next_dawn - <on-change> [Home Assistant value]
#   field next_dawn_str - <on-change> [Home Assistant value]
#   field next_dusk - <on-change> [Home Assistant value]
#   field next_dusk_str - <on-change> [Home Assistant value]
#   field next_rising - <on-change> [Home Assistant value]
#   field next_rising_str - <on-change> [Home Assistant value]
#   field next_setting - <on-change> [Home Assistant value]
#   field next_setting_str - <on-change> [Home Assistant value]
#   field rising - <on-change> [Home Assistant value]
#   field state - <on-change> [Home Assistant value]
#   field value - <on-change> [Home Assistant value]

sun,
  module=homeassistant,
  entity_id=<string>
    azimuth=<float>,
    elevation=<float>,
    next_dawn=<float>,
    next_dusk=<float>,
    next_rising=<float>,
    next_setting=<float>,
    rising=<float>,
    value=<float>
  <timestamp>
