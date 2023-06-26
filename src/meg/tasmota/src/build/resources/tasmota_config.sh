#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################

echo 'Porcessing config for device [rack_fans]' && decode-config.py -s 10.0.6.93 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans.json
