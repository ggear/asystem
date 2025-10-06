#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
if netcat -zw 1 10.0.4.78 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [deck_freezer_plug] at [10.0.4.78] ... '
	kasa --host 10.0.4.78 --type plug alias 'Deck Freezer Plug'
	kasa --host 10.0.4.78 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [deck_freezer_plug] at [http://10.0.4.78/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.79 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [server_jen_plug] at [10.0.4.79] ... '
	kasa --host 10.0.4.79 --type plug alias 'Server Jen Plug'
	kasa --host 10.0.4.79 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [server_jen_plug] at [http://10.0.4.79/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.80 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [lounge_tv_plug] at [10.0.4.80] ... '
	kasa --host 10.0.4.80 --type plug alias 'Lounge Tv Plug'
	kasa --host 10.0.4.80 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [lounge_tv_plug] at [http://10.0.4.80/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.81 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [bathroom_rails_plug] at [10.0.4.81] ... '
	kasa --host 10.0.4.81 --type plug alias 'Bathroom Rails Plug'
	kasa --host 10.0.4.81 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [bathroom_rails_plug] at [http://10.0.4.81/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.84 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [kitchen_coffee_machine_plug] at [10.0.4.84] ... '
	kasa --host 10.0.4.84 --type plug alias 'Kitchen Coffee Machine Plug'
	kasa --host 10.0.4.84 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [kitchen_coffee_machine_plug] at [http://10.0.4.84/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.86 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [kitchen_dish_washer_plug] at [10.0.4.86] ... '
	kasa --host 10.0.4.86 --type plug alias 'Kitchen Dish Washer Plug'
	kasa --host 10.0.4.86 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [kitchen_dish_washer_plug] at [http://10.0.4.86/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.87 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [garden_sewerage_blower_plug] at [10.0.4.87] ... '
	kasa --host 10.0.4.87 --type plug alias 'Garden Sewerage Blower Plug'
	kasa --host 10.0.4.87 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [garden_sewerage_blower_plug] at [http://10.0.4.87/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.4.93 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [rack_backup_plug] at [10.0.4.93] ... '
	kasa --host 10.0.4.93 --type plug alias 'Rack Backup Plug'
	kasa --host 10.0.4.93 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [rack_backup_plug] at [http://10.0.4.93/?] given it is unresponsive'
fi
echo ''