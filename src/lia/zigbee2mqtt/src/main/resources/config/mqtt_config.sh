#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
while [ $(mosquitto_sub -h ${VERNEMQ_IP} -p ${VERNEMQ_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null | grep online | wc -l) -ne 1 ]; do :; done

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Ada Lamp Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 500, "color_temp_startup": 500 }' && echo 'Device [Ada Lamp Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ada Lamp Bulb 1" }' && echo 'Device [Ada Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Ada Lamp", "device": "Ada Lamp Bulb 1" }' && echo 'Device [Ada Lamp Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Edwin Lamp Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Edwin Lamp Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Edwin Lamp Bulb 1" }' && echo 'Device [Edwin Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Edwin Lamp", "device": "Edwin Lamp Bulb 1" }' && echo 'Device [Edwin Lamp Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Edwin Night Light Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 500, "color_temp_startup": 500 }' && echo 'Device [Edwin Night Light Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Edwin Night Light Bulb 1" }' && echo 'Device [Edwin Night Light Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Edwin Night Light", "device": "Edwin Night Light Bulb 1" }' && echo 'Device [Edwin Night Light Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Hallway Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Hallway Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 1" }' && echo 'Device [Hallway Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Main", "device": "Hallway Main Bulb 1" }' && echo 'Device [Hallway Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Hallway Main Bulb 2/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Hallway Main Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 2" }' && echo 'Device [Hallway Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Main", "device": "Hallway Main Bulb 2" }' && echo 'Device [Hallway Main Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Hallway Main Bulb 3/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Hallway Main Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 3" }' && echo 'Device [Hallway Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Main", "device": "Hallway Main Bulb 3" }' && echo 'Device [Hallway Main Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Hallway Main Bulb 4/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Hallway Main Bulb 4] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 4" }' && echo 'Device [Hallway Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Main", "device": "Hallway Main Bulb 4" }' && echo 'Device [Hallway Main Bulb 4] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 1" }' && echo 'Device [Hallway Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Sconces", "device": "Hallway Sconces Bulb 1" }' && echo 'Device [Hallway Sconces Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 2" }' && echo 'Device [Hallway Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Hallway Sconces", "device": "Hallway Sconces Bulb 2" }' && echo 'Device [Hallway Sconces Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 1" }' && echo 'Device [Dining Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 1" }' && echo 'Device [Dining Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 2/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 2" }' && echo 'Device [Dining Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 2" }' && echo 'Device [Dining Main Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 3/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 3" }' && echo 'Device [Dining Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 3" }' && echo 'Device [Dining Main Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 4/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 4] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 4" }' && echo 'Device [Dining Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 4" }' && echo 'Device [Dining Main Bulb 4] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 5/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 5] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 5" }' && echo 'Device [Dining Main Bulb 5] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 5" }' && echo 'Device [Dining Main Bulb 5] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Dining Main Bulb 6/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Dining Main Bulb 6] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 6" }' && echo 'Device [Dining Main Bulb 6] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Dining Main", "device": "Dining Main Bulb 6" }' && echo 'Device [Dining Main Bulb 6] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Lounge Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Lounge Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 1" }' && echo 'Device [Lounge Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Lounge Main", "device": "Lounge Main Bulb 1" }' && echo 'Device [Lounge Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Lounge Main Bulb 2/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Lounge Main Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 2" }' && echo 'Device [Lounge Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Lounge Main", "device": "Lounge Main Bulb 2" }' && echo 'Device [Lounge Main Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Lounge Main Bulb 3/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Lounge Main Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 3" }' && echo 'Device [Lounge Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Lounge Main", "device": "Lounge Main Bulb 3" }' && echo 'Device [Lounge Main Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Lounge Lamp Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 500, "color_temp_startup": 500 }' && echo 'Device [Lounge Lamp Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Lamp Bulb 1" }' && echo 'Device [Lounge Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Lounge Lamp", "device": "Lounge Lamp Bulb 1" }' && echo 'Device [Lounge Lamp Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Parents Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Parents Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 1" }' && echo 'Device [Parents Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Parents Main", "device": "Parents Main Bulb 1" }' && echo 'Device [Parents Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Parents Main Bulb 2/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Parents Main Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 2" }' && echo 'Device [Parents Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Parents Main", "device": "Parents Main Bulb 2" }' && echo 'Device [Parents Main Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Parents Main Bulb 3/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Parents Main Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 3" }' && echo 'Device [Parents Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Parents Main", "device": "Parents Main Bulb 3" }' && echo 'Device [Parents Main Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Sconces Jane Bulb 1" }' && echo 'Device [Parents Sconces Jane Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Parents Sconces", "device": "Parents Sconces Jane Bulb 1" }' && echo 'Device [Parents Sconces Jane Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Sconces Graham Bulb 1" }' && echo 'Device [Parents Sconces Graham Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Parents Sconces", "device": "Parents Sconces Graham Bulb 1" }' && echo 'Device [Parents Sconces Graham Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Study Lamp Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 500, "color_temp_startup": 500 }' && echo 'Device [Study Lamp Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Study Lamp Bulb 1" }' && echo 'Device [Study Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Study Lamp", "device": "Study Lamp Bulb 1" }' && echo 'Device [Study Lamp Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Kitchen Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Kitchen Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 1" }' && echo 'Device [Kitchen Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Kitchen Main", "device": "Kitchen Main Bulb 1" }' && echo 'Device [Kitchen Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Kitchen Main Bulb 2/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Kitchen Main Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 2" }' && echo 'Device [Kitchen Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Kitchen Main", "device": "Kitchen Main Bulb 2" }' && echo 'Device [Kitchen Main Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Kitchen Main Bulb 3/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Kitchen Main Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 3" }' && echo 'Device [Kitchen Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Kitchen Main", "device": "Kitchen Main Bulb 3" }' && echo 'Device [Kitchen Main Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Kitchen Main Bulb 4/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Kitchen Main Bulb 4] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 4" }' && echo 'Device [Kitchen Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Kitchen Main", "device": "Kitchen Main Bulb 4" }' && echo 'Device [Kitchen Main Bulb 4] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Laundry Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Laundry Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Laundry Main Bulb 1" }' && echo 'Device [Laundry Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Laundry Main", "device": "Laundry Main Bulb 1" }' && echo 'Device [Laundry Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Pantry Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Pantry Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Pantry Main Bulb 1" }' && echo 'Device [Pantry Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Pantry Main", "device": "Pantry Main Bulb 1" }' && echo 'Device [Pantry Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Office Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 254, "hue_power_on_color_temperature": 250, "color_temp_startup": 250 }' && echo 'Device [Office Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Office Main Bulb 1" }' && echo 'Device [Office Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Office Main", "device": "Office Main Bulb 1" }' && echo 'Device [Office Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Bathroom Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Bathroom Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Main Bulb 1" }' && echo 'Device [Bathroom Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Bathroom Main", "device": "Bathroom Main Bulb 1" }' && echo 'Device [Bathroom Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 1" }' && echo 'Device [Bathroom Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Bathroom Sconces", "device": "Bathroom Sconces Bulb 1" }' && echo 'Device [Bathroom Sconces Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 2" }' && echo 'Device [Bathroom Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Bathroom Sconces", "device": "Bathroom Sconces Bulb 2" }' && echo 'Device [Bathroom Sconces Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Ensuite Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Ensuite Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Main Bulb 1" }' && echo 'Device [Ensuite Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Ensuite Main", "device": "Ensuite Main Bulb 1" }' && echo 'Device [Ensuite Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 1" }' && echo 'Device [Ensuite Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Ensuite Sconces", "device": "Ensuite Sconces Bulb 1" }' && echo 'Device [Ensuite Sconces Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 2" }' && echo 'Device [Ensuite Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Ensuite Sconces", "device": "Ensuite Sconces Bulb 2" }' && echo 'Device [Ensuite Sconces Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 3" }' && echo 'Device [Ensuite Sconces Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Ensuite Sconces", "device": "Ensuite Sconces Bulb 3" }' && echo 'Device [Ensuite Sconces Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Wardrobe Main Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 3, "hue_power_on_color_temperature": 65535, "color_temp_startup": 65535 }' && echo 'Device [Wardrobe Main Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Wardrobe Main Bulb 1" }' && echo 'Device [Wardrobe Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Wardrobe Main", "device": "Wardrobe Main Bulb 1" }' && echo 'Device [Wardrobe Main Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Garden Pedestals Bulb 1/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Garden Pedestals Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 1" }' && echo 'Device [Garden Pedestals Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Garden Pedestals", "device": "Garden Pedestals Bulb 1" }' && echo 'Device [Garden Pedestals Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Garden Pedestals Bulb 2/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Garden Pedestals Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 2" }' && echo 'Device [Garden Pedestals Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Garden Pedestals", "device": "Garden Pedestals Bulb 2" }' && echo 'Device [Garden Pedestals Bulb 2] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Garden Pedestals Bulb 3/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Garden Pedestals Bulb 3] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 3" }' && echo 'Device [Garden Pedestals Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Garden Pedestals", "device": "Garden Pedestals Bulb 3" }' && echo 'Device [Garden Pedestals Bulb 3] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Garden Pedestals Bulb 4/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Garden Pedestals Bulb 4] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 4" }' && echo 'Device [Garden Pedestals Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Garden Pedestals", "device": "Garden Pedestals Bulb 4" }' && echo 'Device [Garden Pedestals Bulb 4] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Tree Spotlights Bulb 1/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Tree Spotlights Bulb 1] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Tree Spotlights Bulb 1" }' && echo 'Device [Tree Spotlights Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Tree Spotlights", "device": "Tree Spotlights Bulb 1" }' && echo 'Device [Tree Spotlights Bulb 1] added to group' && sleep 1

mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/Tree Spotlights Bulb 2/set' -m '{ "hue_power_on_behavior": "off" }' && echo 'Device [Tree Spotlights Bulb 2] config persisted' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Tree Spotlights Bulb 2" }' && echo 'Device [Tree Spotlights Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/add' -m '{ "group": "Tree Spotlights", "device": "Tree Spotlights Bulb 2" }' && echo 'Device [Tree Spotlights Bulb 2] added to group' && sleep 1

