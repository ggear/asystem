#!/bin/bash
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
echo ''
if netcat -zw 1 10.0.4.100 80 2>/dev/null; then
	echo 'Processing config for device [ceiling_water_booster_plug] at [http://10.0.4.100/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.100 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/ceiling_water_booster_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.100 80 2>/dev/null; do echo 'Waiting for device [ceiling_water_booster_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":25}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [25] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta1 25'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [25]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta2 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerDelta3 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerLow' | grep '{"PowerLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerLow 0'
		echo ''
	else
		echo 'Config set skipped, [PowerLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerHigh' | grep '{"PowerHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=PowerHigh 0'
		echo ''
	else
		echo 'Config set skipped, [PowerHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=VoltageLow' | grep '{"VoltageLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=VoltageLow 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=VoltageHigh' | grep '{"VoltageHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=VoltageHigh 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=CurrentLow' | grep '{"CurrentLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=CurrentLow 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=CurrentHigh' | grep '{"CurrentHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=CurrentHigh 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentHigh] already set to [0]'
	fi
	printf 'Restarting [ceiling_water_booster_plug] with response: ' && curl -s -m 5 http://10.0.4.100/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.100 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [ceiling_water_booster_plug] at [http://10.0.4.100/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.101 80 2>/dev/null; then
	echo 'Processing config for device [rack_fans_plug] at [http://10.0.4.101/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.101 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_fans_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.101 80 2>/dev/null; do echo 'Waiting for device [rack_fans_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	printf 'Restarting [rack_fans_plug] with response: ' && curl -s -m 5 http://10.0.4.101/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.101 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [rack_fans_plug] at [http://10.0.4.101/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.102 80 2>/dev/null; then
	echo 'Processing config for device [rack_outlet_plug] at [http://10.0.4.102/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.102 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/rack_outlet_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.102 80 2>/dev/null; do echo 'Waiting for device [rack_outlet_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [1] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerOnState 1'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [1]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":25}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [25] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta1 25'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [25]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta2 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerDelta3 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerLow' | grep '{"PowerLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerLow 0'
		echo ''
	else
		echo 'Config set skipped, [PowerLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerHigh' | grep '{"PowerHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=PowerHigh 0'
		echo ''
	else
		echo 'Config set skipped, [PowerHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=VoltageLow' | grep '{"VoltageLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=VoltageLow 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=VoltageHigh' | grep '{"VoltageHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=VoltageHigh 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=CurrentLow' | grep '{"CurrentLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=CurrentLow 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=CurrentHigh' | grep '{"CurrentHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=CurrentHigh 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentHigh] already set to [0]'
	fi
	printf 'Restarting [rack_outlet_plug] with response: ' && curl -s -m 5 http://10.0.4.102/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.102 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [rack_outlet_plug] at [http://10.0.4.102/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.103 80 2>/dev/null; then
	echo 'Processing config for device [kitchen_bench_lights_plug] at [http://10.0.4.103/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.103 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/kitchen_bench_lights_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.103 80 2>/dev/null; do echo 'Waiting for device [kitchen_bench_lights_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [1] with response: ' && curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=PowerOnState 1'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [1]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	printf 'Restarting [kitchen_bench_lights_plug] with response: ' && curl -s -m 5 http://10.0.4.103/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.103 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [kitchen_bench_lights_plug] at [http://10.0.4.103/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.104 80 2>/dev/null; then
	echo 'Processing config for device [kitchen_fan_plug] at [http://10.0.4.104/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.104 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/kitchen_fan_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.104 80 2>/dev/null; do echo 'Waiting for device [kitchen_fan_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":25}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [25] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta1 25'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [25]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta2 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerDelta3 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerLow' | grep '{"PowerLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerLow 0'
		echo ''
	else
		echo 'Config set skipped, [PowerLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerHigh' | grep '{"PowerHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=PowerHigh 0'
		echo ''
	else
		echo 'Config set skipped, [PowerHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=VoltageLow' | grep '{"VoltageLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=VoltageLow 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=VoltageHigh' | grep '{"VoltageHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=VoltageHigh 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=CurrentLow' | grep '{"CurrentLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=CurrentLow 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=CurrentHigh' | grep '{"CurrentHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=CurrentHigh 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentHigh] already set to [0]'
	fi
	printf 'Restarting [kitchen_fan_plug] with response: ' && curl -s -m 5 http://10.0.4.104/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.104 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [kitchen_fan_plug] at [http://10.0.4.104/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.105 80 2>/dev/null; then
	echo 'Processing config for device [ceiling_network_switch_plug] at [http://10.0.4.105/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.105 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/ceiling_network_switch_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.105 80 2>/dev/null; do echo 'Waiting for device [ceiling_network_switch_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":1}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [1] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerOnState 1'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [1]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":25}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [25] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta1 25'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [25]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta2 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerDelta3 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerLow' | grep '{"PowerLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerLow 0'
		echo ''
	else
		echo 'Config set skipped, [PowerLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerHigh' | grep '{"PowerHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=PowerHigh 0'
		echo ''
	else
		echo 'Config set skipped, [PowerHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=VoltageLow' | grep '{"VoltageLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=VoltageLow 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=VoltageHigh' | grep '{"VoltageHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=VoltageHigh 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=CurrentLow' | grep '{"CurrentLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=CurrentLow 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=CurrentHigh' | grep '{"CurrentHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=CurrentHigh 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentHigh] already set to [0]'
	fi
	printf 'Restarting [ceiling_network_switch_plug] with response: ' && curl -s -m 5 http://10.0.4.105/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.105 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [ceiling_network_switch_plug] at [http://10.0.4.105/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.106 80 2>/dev/null; then
	echo 'Processing config for device [garden_pool_filter_plug] at [http://10.0.4.106/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.106 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/garden_pool_filter_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.106 80 2>/dev/null; do echo 'Waiting for device [garden_pool_filter_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta1' | grep '{"PowerDelta1":25}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta1] to [25] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta1 25'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta1] already set to [25]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta2' | grep '{"PowerDelta2":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta2] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta2 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta2] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta3' | grep '{"PowerDelta3":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerDelta3] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerDelta3 0'
		echo ''
	else
		echo 'Config set skipped, [PowerDelta3] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerLow' | grep '{"PowerLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerLow 0'
		echo ''
	else
		echo 'Config set skipped, [PowerLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerHigh' | grep '{"PowerHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=PowerHigh 0'
		echo ''
	else
		echo 'Config set skipped, [PowerHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=VoltageLow' | grep '{"VoltageLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=VoltageLow 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=VoltageHigh' | grep '{"VoltageHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [VoltageHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=VoltageHigh 0'
		echo ''
	else
		echo 'Config set skipped, [VoltageHigh] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=CurrentLow' | grep '{"CurrentLow":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentLow] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=CurrentLow 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentLow] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=CurrentHigh' | grep '{"CurrentHigh":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [CurrentHigh] to [0] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=CurrentHigh 0'
		echo ''
	else
		echo 'Config set skipped, [CurrentHigh] already set to [0]'
	fi
	printf 'Restarting [garden_pool_filter_plug] with response: ' && curl -s -m 5 http://10.0.4.106/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.106 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [garden_pool_filter_plug] at [http://10.0.4.106/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.107 80 2>/dev/null; then
	echo 'Processing config for device [deck_festoons_plug] at [http://10.0.4.107/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.107 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/deck_festoons_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.107 80 2>/dev/null; do echo 'Waiting for device [deck_festoons_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	printf 'Restarting [deck_festoons_plug] with response: ' && curl -s -m 5 http://10.0.4.107/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.107 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [deck_festoons_plug] at [http://10.0.4.107/?] given it is unresponsive'
fi
echo ''
if netcat -zw 1 10.0.4.108 80 2>/dev/null; then
	echo 'Processing config for device [landing_festoons_plug] at [http://10.0.4.108/?] ... '
	echo 'Current firmware ['"$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\()"'] versus required [13.0.0]'
	decode-config.py -s 10.0.4.108 -i /Users/graham/Code/asystem/src/meg/tasmota/src/build/resources/devices/landing_festoons_plug.json
	sleep 1 && while ! netcat -zw 1 10.0.4.108 80 2>/dev/null; do echo 'Waiting for device [landing_festoons_plug] to come up ...' && sleep 1; done
	if [ "$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=PowerOnState' | grep '{"PowerOnState":0}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerOnState] to [0] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=PowerOnState 0'
		echo ''
	else
		echo 'Config set skipped, [PowerOnState] already set to [0]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=PowerRetain' | grep '{"PowerRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [PowerRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=PowerRetain ON'
		echo ''
	else
		echo 'Config set skipped, [PowerRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=StatusRetain' | grep '{"StatusRetain":"ON"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [StatusRetain] to [ON] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=StatusRetain ON'
		echo ''
	else
		echo 'Config set skipped, [StatusRetain] already set to [ON]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=SensorRetain' | grep '{"SensorRetain":"OFF"}' | wc -l)" -ne 1 ]; then
		printf 'Config set [SensorRetain] to [OFF] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=SensorRetain OFF'
		echo ''
	else
		echo 'Config set skipped, [SensorRetain] already set to [OFF]'
	fi
	if [ "$(curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=TelePeriod' | grep '{"TelePeriod":10}' | wc -l)" -ne 1 ]; then
		printf 'Config set [TelePeriod] to [10] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=TelePeriod 10'
		echo ''
	else
		echo 'Config set skipped, [TelePeriod] already set to [10]'
	fi
	printf 'Restarting [landing_festoons_plug] with response: ' && curl -s -m 5 http://10.0.4.108/cm? --data-urlencode 'cmnd=Restart 1'
	printf '
'
	printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 10.0.4.108 80 2>/dev/null; do printf '.' && sleep 1; done
	printf ' done
'
else
	echo 'Skipping config for device [landing_festoons_plug] at [http://10.0.4.108/?] given it is unresponsive'
fi
echo ''
