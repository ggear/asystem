#!/usr/bin/env python

import json
import os
import sys
import threading
from typing import Any
from typing import Optional

from paho.mqtt.client import Client

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: ./{} <device-address> <device-friendly-name> <group-friendly-name> <device-config-json>".format(
            os.path.basename(sys.argv[0])))
        exit(1)

    device_address = sys.argv[1]
    device_name = sys.argv[2]
    device_group = sys.argv[3]
    device_config = sys.argv[4]
    device_config_group = '{{ "group": "{}", "device": "{}" }}'.format(device_group, device_name)
    mqtt_host = os.environ["VERNEMQ_IP"]
    mqtt_port = int(os.environ["VERNEMQ_PORT"])


    def _set(topic: str, message: str, **mqtt_kwargs):

        def on_publish(client, userdata):
            client.disconnect()
            if userdata["lock"]:
                userdata["lock"].release()
            return

        lock: Optional[threading.Lock]
        lock = threading.Lock()
        userdata: dict[str, Any] = {
            "lock": lock,
        }
        client = Client(userdata=userdata)
        client.on_publish = on_publish
        client.connect(mqtt_host, mqtt_port)
        assert lock is not None
        lock.acquire()
        code = client.publish(topic, message, mqtt_kwargs.pop("qos", 0))
        client.loop_start()
        lock.acquire(timeout=1)
        client.loop_stop()
        client.disconnect()
        return code[0]


    def _get(topic: str, **mqtt_kwargs):

        def on_connect(client, userdata, flags, rc):
            client.subscribe(userdata["topic"])
            return

        def on_message(client, userdata, message):
            userdata["messages"] = message
            client.disconnect()
            if userdata["lock"]:
                userdata["lock"].release()
            return

        lock: Optional[threading.Lock]
        lock = threading.Lock()
        userdata: dict[str, Any] = {
            "topic": [(topic, mqtt_kwargs.pop("qos", 0))],
            "messages": None,
            "lock": lock,
        }
        client = Client(userdata=userdata)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_host, mqtt_port)
        assert lock is not None
        lock.acquire()
        client.loop_start()
        lock.acquire(timeout=1)
        client.loop_stop()
        client.disconnect()
        return None if userdata["messages"] is None else json.loads(userdata["messages"].payload)


    device_availability_dict = _get("zigbee/{}/availability".format(device_name))
    if device_availability_dict is not None and device_availability_dict["state"] == "online":
        grouped = False
        group_dict = None
        groups_dict = _get("zigbee/bridge/groups")
        for group_dict in groups_dict:
            if "friendly_name" in group_dict and group_dict["friendly_name"] == device_group:
                break
        if group_dict is not None and "members" in group_dict:
            for group_member_dict in group_dict["members"]:
                if "ieee_address" in group_member_dict and group_member_dict["ieee_address"] == device_address:
                    grouped = True
                    break
        if grouped:
            print("Device [{}] already configured, no action required [SUCCESS]".format(device_name))
        else:
            if device_config != "":
                print("Device [{}] config pushed [{}]"
                      .format(device_name,
                              "SUCCESS" if _set("zigbee/{}/set".format(device_name), device_config) == 0 else "FAILED"))
            print("Device [{}] added to group [{}] [{}]"
                  .format(device_name, device_group,
                          "SUCCESS" if _set("zigbee/bridge/request/group/members/add"
                                            .format(device_name), device_config_group) == 0 else "FAILED"))
        for group_dict in groups_dict:
            if "friendly_name" in group_dict and group_dict["friendly_name"] != device_group:
                if "members" in group_dict:
                    for group_member_dict in group_dict["members"]:
                        if "ieee_address" in group_member_dict and group_member_dict["ieee_address"] == device_address:
                            print("Device [{}] removed from group [{}] [{}]"
                                  .format(device_name, device_group,
                                          "SUCCESS" if _set("zigbee2mqtt/bridge/request/group/members/remove"
                                                            .format(device_name), device_config_group) == 0 else "FAILED"))
    else:
        print("Device [{}] not available currently, skipping config [SUCCESS]".format(device_name))
