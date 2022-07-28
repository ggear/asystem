#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
mosquitto_pub -h $VERNEMQ_IP -p $VERNEMQ_PORT -t 'Edwin Lamp Bulb 1/set' -m '{ "hue_power_on_behavior": "on", "hue_power_on_brightness": 1, "hue_power_on_color_temperature": 454, "color_temp_startup": 65535 }'
