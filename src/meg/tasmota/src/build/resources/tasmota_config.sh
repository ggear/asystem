#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################

echo 'Processing config for device [rack_fans] at [http://10.0.6.93/cn] ... '
decode-config.py -s 10.0.6.93 -o /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans-backup.json --json-indent 2
decode-config.py -s 10.0.6.93 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans.json
