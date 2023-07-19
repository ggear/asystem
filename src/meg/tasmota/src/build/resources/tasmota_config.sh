#!/bin/bash
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
echo ''
if netcat -zw 1 10.0.6.100 80 2>/dev/null; then
	echo 'Processing config for device [roof_water_heater_booster_plug] at [http://10.0.6.100/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.100 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/roof_water_heater_booster_plug.json || true
	sleep 1 && while ! netcat -zw 1 10.0.6.100 80 2>/dev/null; do echo 'Waiting for device [roof_water_heater_booster_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [1] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta1 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [1] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta2 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [1] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=PowerDelta3 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [1]'
	fi
	printf 'Restarting [roof_water_heater_booster_plug] with response: ' && curl -s http://10.0.6.100/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.6.100 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [roof_water_heater_booster_plug] at [http://10.0.6.100/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.6.101 80 2>/dev/null; then
	echo 'Processing config for device [rack_fans_plug] at [http://10.0.6.101/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.101 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans_plug.json || true
	sleep 1 && while ! netcat -zw 1 10.0.6.101 80 2>/dev/null; do echo 'Waiting for device [rack_fans_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	printf 'Restarting [rack_fans_plug] with response: ' && curl -s http://10.0.6.101/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.6.101 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [rack_fans_plug] at [http://10.0.6.101/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.6.102 80 2>/dev/null; then
	echo 'Processing config for device [rack_outlet_plug] at [http://10.0.6.102/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.102 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_outlet_plug.json || true
	sleep 1 && while ! netcat -zw 1 10.0.6.102 80 2>/dev/null; do echo 'Waiting for device [rack_outlet_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [1] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerOnState 1'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [1] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta1 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [1] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta2 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [1] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=PowerDelta3 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [1]'
	fi
	printf 'Restarting [rack_outlet_plug] with response: ' && curl -s http://10.0.6.102/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.6.102 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [rack_outlet_plug] at [http://10.0.6.102/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.6.103 80 2>/dev/null; then
	echo 'Processing config for device [kitchen_downlights_plug] at [http://10.0.6.103/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.103 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/kitchen_downlights_plug.json || true
	sleep 1 && while ! netcat -zw 1 10.0.6.103 80 2>/dev/null; do echo 'Waiting for device [kitchen_downlights_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [1] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerOnState 1'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [1] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta1 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [1] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta2 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [1] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=PowerDelta3 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [1]'
	fi
	printf 'Restarting [kitchen_downlights_plug] with response: ' && curl -s http://10.0.6.103/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.6.103 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [kitchen_downlights_plug] at [http://10.0.6.103/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.6.104 80 2>/dev/null; then
	echo 'Processing config for device [kitchen_fan_plug] at [http://10.0.6.104/?] ... '
	echo 'Current firmware ['"$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.6.104 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/kitchen_fan_plug.json || true
	sleep 1 && while ! netcat -zw 1 10.0.6.104 80 2>/dev/null; do echo 'Waiting for device [kitchen_fan_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [1] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta1 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [1] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta2 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [1]'
	fi
	if [ "$(curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [1] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=PowerDelta3 1'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [1]'
	fi
	printf 'Restarting [kitchen_fan_plug] with response: ' && curl -s http://10.0.6.104/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.6.104 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [kitchen_fan_plug] at [http://10.0.6.104/?] given it is unresponsive'
fi
echo ''
