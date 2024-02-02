#!/usr/bin/env python

import json
import os
import sys
import threading
import time
from typing import Any
from typing import Optional

from paho.mqtt.client import Client

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: ./{} <device-ieee-address> <device-friendly-name> <group-friendly-name> <device-config-json>"
              .format(os.path.basename(sys.argv[0])))
        exit(1)

    device_address = sys.argv[1]
    device_name = sys.argv[2]
    device_group = sys.argv[3]
    device_config = sys.argv[4]
    device_config_group = '{{ "group": "{}", "device": "{}" }}'.format(device_group, device_name)
    mqtt_host = os.environ["VERNEMQ_HOST"]
    mqtt_port = int(os.environ["VERNEMQ_PORT"])


    def _mqtt_pub(topic: str, message: str, **mqtt_kwargs):

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


    def _mqtt_sub(topic: str, **mqtt_kwargs):

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


    def _device_available():
        device_availability_dict = _mqtt_sub("zigbee/{}/availability".format(device_name))
        return device_availability_dict is not None and device_availability_dict["state"] == "online"


    def _device_config():
        grouped = False
        group_dict = None
        for group_dict in _mqtt_sub("zigbee/bridge/groups"):
            if "friendly_name" in group_dict and group_dict["friendly_name"] == device_group:
                break
        if group_dict is not None and "members" in group_dict:
            for group_member_dict in group_dict["members"]:
                if "ieee_address" in group_member_dict and group_member_dict["ieee_address"] == device_address:
                    grouped = True
                    break
        if grouped:
            print("[INFO] Device [{}] configured, no action required".format(device_name))
            return
        else:
            if device_config != "":
                print("[{}] Device [{}] config command pushed".format(
                    "INFO" if _mqtt_pub("zigbee/{}/set".format(device_name), device_config) == 0 \
                        else "WARN",
                    device_name,
                ))
            print("[{}] Device [{}] group [{}] add command pushed".format(
                "INFO" if _mqtt_pub("zigbee/bridge/request/group/members/add", device_config_group) == 0 \
                    else "WARN",
                device_name,
                device_group,
            ))
            time.sleep(2)
            return _device_config()


    def _device_clean():
        for group_dict in _mqtt_sub("zigbee/bridge/groups"):
            if "friendly_name" in group_dict and group_dict["friendly_name"] != device_group:
                if "members" in group_dict:
                    for group_member_dict in group_dict["members"]:
                        if "ieee_address" in group_member_dict and group_member_dict["ieee_address"] == device_address:
                            print("[{}] Device [{}] group [{}] remove command pushed".format(
                                "INFO" if _mqtt_pub("zigbee2mqtt/bridge/request/group/members/remove", device_config_group) == 0 \
                                    else "WARN",
                                device_name,
                                device_group,
                            ))
                            _device_clean()


    def _device_verify():
        for group_dict in _mqtt_sub("zigbee/bridge/groups"):
            if "friendly_name" in group_dict and group_dict["friendly_name"] == device_group:
                if "members" in group_dict and len(group_dict["members"]) == 0:
                    print("------\n[FAIL] Device [{}] group [{}] does not have any member devices\n------".format(
                        device_name,
                        group_dict["friendly_name"]
                    ))


    def _device_skip():
        print("[INFO] Device [{}] not available currently, skipping config".format(device_name))


    if _device_available():
        _device_clean()
        _device_config()
    else:
        _device_skip()
    _device_verify()
