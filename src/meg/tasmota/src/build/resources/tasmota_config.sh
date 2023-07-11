#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
echo '' && echo 'Processing config for device [rack_fans_plug] at [http://10.0.6.93/?] ... '
echo 'Current firmware ['$(curl -s --connect-timeout 1 http://10.0.6.93/cm?cmnd=Status%202 | jq -r .StatusFWR.Version | cut -f1 -d\()'] versus required [13.0.0]'
decode-config.py -s 10.0.6.93 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans_plug.json || true
echo '' && echo 'Processing config for device [roof_water_heater_booster_plug] at [http://10.0.6.94/?] ... '
echo 'Current firmware ['$(curl -s --connect-timeout 1 http://10.0.6.94/cm?cmnd=Status%202 | jq -r .StatusFWR.Version | cut -f1 -d\()'] versus required [13.0.0]'
decode-config.py -s 10.0.6.94 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/roof_water_heater_booster_plug.json || true
echo ''