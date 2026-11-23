################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# zigbee/experience [mesh experience, one row per part of the mesh]
#   cadence 15m
#   tag module [always 'network']
#   tag experience* [router is the always on outlets weighted by availability, mesh is every available device:
#     router,
#     mesh]
#   field experience_pct % 15m [share of full link quality across that part of the mesh]

zigbee,
  module=network,
  experience=<string>
    experience_pct=<float>
  <timestamp>
