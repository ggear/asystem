#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
if netcat -zw 1 10.0.6.70 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [lounge_sub_plug] at [10.0.6.70] ... '
	kasa --host 10.0.6.70 --type plug alias 'Lounge Sub Plug'
	kasa --host 10.0.6.70 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [lounge_sub_plug] at [http://10.0.6.70/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.71 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [study_battery_charger_plug] at [10.0.6.71] ... '
	kasa --host 10.0.6.71 --type plug alias 'Study Battery Charger Plug'
	kasa --host 10.0.6.71 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [study_battery_charger_plug] at [http://10.0.6.71/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.72 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [laundry_vacuum_charger_plug] at [10.0.6.72] ... '
	kasa --host 10.0.6.72 --type plug alias 'Laundry Vacuum Charger Plug'
	kasa --host 10.0.6.72 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [laundry_vacuum_charger_plug] at [http://10.0.6.72/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.73 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [kitchen_dish_washer_plug] at [10.0.6.73] ... '
	kasa --host 10.0.6.73 --type plug alias 'Kitchen Dish Washer Plug'
	kasa --host 10.0.6.73 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [kitchen_dish_washer_plug] at [http://10.0.6.73/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.74 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [laundry_clothes_dryer_plug] at [10.0.6.74] ... '
	kasa --host 10.0.6.74 --type plug alias 'Laundry Clothes Dryer Plug'
	kasa --host 10.0.6.74 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [laundry_clothes_dryer_plug] at [http://10.0.6.74/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.75 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [laundry_washing_machine_plug] at [10.0.6.75] ... '
	kasa --host 10.0.6.75 --type plug alias 'Laundry Washing Machine Plug'
	kasa --host 10.0.6.75 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [laundry_washing_machine_plug] at [http://10.0.6.75/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.76 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [kitchen_coffee_machine_plug] at [10.0.6.76] ... '
	kasa --host 10.0.6.76 --type plug alias 'Kitchen Coffee Machine Plug'
	kasa --host 10.0.6.76 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [kitchen_coffee_machine_plug] at [http://10.0.6.76/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.77 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [kitchen_fridge_plug] at [10.0.6.77] ... '
	kasa --host 10.0.6.77 --type plug alias 'Kitchen Fridge Plug'
	kasa --host 10.0.6.77 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [kitchen_fridge_plug] at [http://10.0.6.77/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.78 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [deck_freezer_plug] at [10.0.6.78] ... '
	kasa --host 10.0.6.78 --type plug alias 'Deck Freezer Plug'
	kasa --host 10.0.6.78 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [deck_freezer_plug] at [http://10.0.6.78/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.79 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [old_kitchen_downlights_plug] at [10.0.6.79] ... '
	kasa --host 10.0.6.79 --type plug alias 'Old Kitchen Downlights Plug'
	kasa --host 10.0.6.79 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [old_kitchen_downlights_plug] at [http://10.0.6.79/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.80 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [lounge_tv_outlet_plug] at [10.0.6.80] ... '
	kasa --host 10.0.6.80 --type plug alias 'Lounge Tv Outlet Plug'
	kasa --host 10.0.6.80 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [lounge_tv_outlet_plug] at [http://10.0.6.80/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.81 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [bathroom_rails_plug] at [10.0.6.81] ... '
	kasa --host 10.0.6.81 --type plug alias 'Bathroom Rails Plug'
	kasa --host 10.0.6.81 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [bathroom_rails_plug] at [http://10.0.6.81/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.82 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [study_outlet_plug] at [10.0.6.82] ... '
	kasa --host 10.0.6.82 --type plug alias 'Study Outlet Plug'
	kasa --host 10.0.6.82 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [study_outlet_plug] at [http://10.0.6.82/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.83 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [office_outlet_plug] at [10.0.6.83] ... '
	kasa --host 10.0.6.83 --type plug alias 'Office Outlet Plug'
	kasa --host 10.0.6.83 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [office_outlet_plug] at [http://10.0.6.83/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.84 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [roof_network_switch_plug] at [10.0.6.84] ... '
	kasa --host 10.0.6.84 --type plug alias 'Roof Network Switch Plug'
	kasa --host 10.0.6.84 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [roof_network_switch_plug] at [http://10.0.6.84/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.85 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [rack_internet_modem_plug] at [10.0.6.85] ... '
	kasa --host 10.0.6.85 --type plug alias 'Rack Internet Modem Plug'
	kasa --host 10.0.6.85 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [rack_internet_modem_plug] at [http://10.0.6.85/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.86 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [old_rack_outlet_plug] at [10.0.6.86] ... '
	kasa --host 10.0.6.86 --type plug alias 'Old Rack Outlet Plug'
	kasa --host 10.0.6.86 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [old_rack_outlet_plug] at [http://10.0.6.86/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.87 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [old_kitchen_fan_plug] at [10.0.6.87] ... '
	kasa --host 10.0.6.87 --type plug alias 'Old Kitchen Fan Plug'
	kasa --host 10.0.6.87 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [old_kitchen_fan_plug] at [http://10.0.6.87/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.88 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [deck_festoons_plug] at [10.0.6.88] ... '
	kasa --host 10.0.6.88 --type plug alias 'Deck Festoons Plug'
	kasa --host 10.0.6.88 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [deck_festoons_plug] at [http://10.0.6.88/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.89 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [landing_festoons_plug] at [10.0.6.89] ... '
	kasa --host 10.0.6.89 --type plug alias 'Landing Festoons Plug'
	kasa --host 10.0.6.89 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [landing_festoons_plug] at [http://10.0.6.89/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.90 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [ada_tablet_outlet_plug] at [10.0.6.90] ... '
	kasa --host 10.0.6.90 --type plug alias 'Ada Tablet Outlet Plug'
	kasa --host 10.0.6.90 --type plug led 'False'
else
	echo '' && echo 'Skipping config for device [ada_tablet_outlet_plug] at [http://10.0.6.90/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.91 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [server_flo_outlet_plug] at [10.0.6.91] ... '
	kasa --host 10.0.6.91 --type plug alias 'Server Flo Outlet Plug'
	kasa --host 10.0.6.91 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [server_flo_outlet_plug] at [http://10.0.6.91/?] given it is unresponsive'
fi
if netcat -zw 1 10.0.6.92 9999 2>/dev/null; then
	echo '' && echo 'Processing config for device [server_meg_outlet_plug] at [10.0.6.92] ... '
	kasa --host 10.0.6.92 --type plug alias 'Server Meg Outlet Plug'
	kasa --host 10.0.6.92 --type plug led 'True'
else
	echo '' && echo 'Skipping config for device [server_meg_outlet_plug] at [http://10.0.6.92/?] given it is unresponsive'
fi
echo ''