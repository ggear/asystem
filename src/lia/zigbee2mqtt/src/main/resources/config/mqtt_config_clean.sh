#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
ROOT_DIR=$(dirname $(readlink -f "$0"))
while [ $(mosquitto_sub -h ${VERNEMQ_IP} -p ${VERNEMQ_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null | grep online | wc -l) -ne 1 ]; do :; done
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ada Lamp Bulb 1" }' && echo '[INFO] Device [Ada Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Edwin Lamp Bulb 1" }' && echo '[INFO] Device [Edwin Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Edwin Night Light Bulb 1" }' && echo '[INFO] Device [Edwin Night Light Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 1" }' && echo '[INFO] Device [Hallway Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 2" }' && echo '[INFO] Device [Hallway Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 3" }' && echo '[INFO] Device [Hallway Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 4" }' && echo '[INFO] Device [Hallway Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 1" }' && echo '[INFO] Device [Hallway Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 2" }' && echo '[INFO] Device [Hallway Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 1" }' && echo '[INFO] Device [Dining Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 2" }' && echo '[INFO] Device [Dining Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 3" }' && echo '[INFO] Device [Dining Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 4" }' && echo '[INFO] Device [Dining Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 5" }' && echo '[INFO] Device [Dining Main Bulb 5] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 6" }' && echo '[INFO] Device [Dining Main Bulb 6] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 1" }' && echo '[INFO] Device [Lounge Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 2" }' && echo '[INFO] Device [Lounge Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 3" }' && echo '[INFO] Device [Lounge Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Lamp Bulb 1" }' && echo '[INFO] Device [Lounge Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 1" }' && echo '[INFO] Device [Parents Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 2" }' && echo '[INFO] Device [Parents Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 3" }' && echo '[INFO] Device [Parents Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Jane Bedside Bulb 1" }' && echo '[INFO] Device [Parents Jane Bedside Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Graham Bedside Bulb 1" }' && echo '[INFO] Device [Parents Graham Bedside Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Study Lamp Bulb 1" }' && echo '[INFO] Device [Study Lamp Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 1" }' && echo '[INFO] Device [Kitchen Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 2" }' && echo '[INFO] Device [Kitchen Main Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 3" }' && echo '[INFO] Device [Kitchen Main Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 4" }' && echo '[INFO] Device [Kitchen Main Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Laundry Main Bulb 1" }' && echo '[INFO] Device [Laundry Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Pantry Main Bulb 1" }' && echo '[INFO] Device [Pantry Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Office Main Bulb 1" }' && echo '[INFO] Device [Office Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Main Bulb 1" }' && echo '[INFO] Device [Bathroom Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 1" }' && echo '[INFO] Device [Bathroom Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 2" }' && echo '[INFO] Device [Bathroom Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Main Bulb 1" }' && echo '[INFO] Device [Ensuite Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 1" }' && echo '[INFO] Device [Ensuite Sconces Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 2" }' && echo '[INFO] Device [Ensuite Sconces Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 3" }' && echo '[INFO] Device [Ensuite Sconces Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Wardrobe Main Bulb 1" }' && echo '[INFO] Device [Wardrobe Main Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 1" }' && echo '[INFO] Device [Garden Pedestals Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 2" }' && echo '[INFO] Device [Garden Pedestals Bulb 2] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 3" }' && echo '[INFO] Device [Garden Pedestals Bulb 3] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Garden Pedestals Bulb 4" }' && echo '[INFO] Device [Garden Pedestals Bulb 4] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Tree Spotlights Bulb 1" }' && echo '[INFO] Device [Tree Spotlights Bulb 1] removed from all groups' && sleep 1
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Tree Spotlights Bulb 2" }' && echo '[INFO] Device [Tree Spotlights Bulb 2] removed from all groups' && sleep 1