#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
echo ''
if netcat -z 10.0.6.93 80 2>/dev/null; then
	echo 'Processing config for device [rack_fans_plug] at [http://10.0.6.93/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.93/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.93 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans_plug.json || true
	while ! netcat -z 10.0.6.93 80 2>/dev/null; do sleep 1; done
	if [ "$(curl -s http://10.0.6.93/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		echo 'Config set [PowerOnState] to [0] with response: ' && curl -s http://10.0.6.93/cm? --data-urlencode 'cmnd=PowerOnState 0'
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
fi
echo ''
if netcat -z 10.0.6.94 80 2>/dev/null; then
	echo 'Processing config for device [roof_water_heater_booster_plug] at [http://10.0.6.94/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.94/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.94 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/roof_water_heater_booster_plug.json || true
	while ! netcat -z 10.0.6.94 80 2>/dev/null; do sleep 1; done
	if [ "$(curl -s http://10.0.6.94/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		echo 'Config set [PowerOnState] to [0] with response: ' && curl -s http://10.0.6.94/cm? --data-urlencode 'cmnd=PowerOnState 0'
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
fi
echo ''
