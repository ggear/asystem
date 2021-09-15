import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/../..".format(os.path.dirname(os.path.realpath(__file__))))
DIR_ROOT = os.path.abspath("{}/../../../../../".format(DIR_MODULE_ROOT))
for dir_module in glob.glob("{}/*/*/".format(DIR_ROOT)):
    if dir_module.split("/")[-2] == "vernemq":
        HOST_VERNEMQ = dir_module.split("/")[-3]
sys.path.insert(0, DIR_MODULE_ROOT)

import json

import sys
import time
from anode.plugin.plugin import Plugin
import paho.mqtt.client as mqtt
import anode
from collections import OrderedDict

TIME_WAIT_SECS = 2

SENSORS = {}
SENSORS_HEADER = [
    "Index ID",
    "Unique ID",
    "Entity ID",
    "Entity Filter",
    "Entity Name",
    "Entity Friendly Name",
    "Entity Domain",
    "Entity Group",
    "Entity Location",
    "Entity Topic"
]

CONFIG = anode.anode.load_config(
    os.path.join(DIR_MODULE_ROOT, "../resources/config/anode.yaml"),
    os.path.join(DIR_MODULE_ROOT, "../../../.env")
)


def on_connect(client, user_data, flags, return_code):
    client.subscribe("{}/#".format(CONFIG["publish_push_metadata_topic"]))


def on_message(client, user_data, message):
    try:
        topic = message.topic.encode("utf-8")
        if len(message.payload) > 0:
            payload = message.payload.decode("unicode-escape").encode("utf-8")
            payload_json = json.loads(payload)
            payload_unicode = "\"" + payload.replace("\"", "\"\"") + "\""
            payload_id = payload_json["unique_id"].encode("utf-8") if "unique_id" in payload_json else ""
            payload_id_tokens = Plugin.datum_field_decode(payload_id).encode("utf-8").split(".") \
                if "unique_id" in payload_json else ()
            payload_id_tokens = [token.replace("-", " ").title() for token in payload_id_tokens]
            if payload_id_tokens:
                sensor_raw = [
                    SENSORS[payload_id][0] if payload_id in SENSORS else "9999999",
                    payload_json["unique_id"].encode("utf-8") if "unique_id" in payload_json else "",
                    payload_json["name"].encode("utf-8").replace(" ", "_").lower() if "name" in payload_json else "",
                    SENSORS[payload_id][3] if payload_id in SENSORS else "Hidden",
                    payload_json["name"].encode("utf-8") if "name" in payload_json else "",
                    payload_id_tokens[1] if len(payload_id_tokens) > 1 else "",
                    payload_id_tokens[2] if len(payload_id_tokens) > 2 else "",
                    payload_id_tokens[3] if len(payload_id_tokens) > 3 else "",
                    payload_id_tokens[4] if len(payload_id_tokens) > 4 else "",
                    topic,
                    payload_unicode
                ]
                SENSORS[payload_id] = sensor_raw[:-1]
        if mode() == "clean":
            client.publish(topic, payload=None, qos=1, retain=True)
    except Exception as exception:
        print(exception)


def load():
    print("Metadata script [anode] sensor load")
    file_sensor = "{}/../resources/metadata/sensor.csv".format(DIR_MODULE_ROOT)
    if os.path.isfile(file_sensor):
        with open(file_sensor, "r") as file:
            lines = iter(file.readlines())
            next(lines)
            for line in lines:
                sensor = line.strip().split(",")
                SENSORS[sensor[1]] = sensor
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print("{}:{}".format(HOST_VERNEMQ, CONFIG["publish_port"]))

    client.connect(HOST_VERNEMQ, CONFIG["publish_port"], 60)
    time_start = time.time()
    while True:
        client.loop()
        time_elapsed = time.time() - time_start
        if time_elapsed > TIME_WAIT_SECS:
            client.disconnect()
            break
    print("Metadata script [anode] sensor refresh")
    sensors = sorted(SENSORS.values(), key=lambda x: x[0].zfill(7) + x[6] + x[8])
    with open(file_sensor, "w") as file:
        for sensor in [SENSORS_HEADER] + sensors:
            file.write("{}\n".format(",".join(sensor)))
    sensors_group_domain = OrderedDict()
    for sensor in sensors:
        if sensor[3] != 'Hidden':
            if sensor[7] not in sensors_group_domain:
                sensors_group_domain[sensor[7]] = OrderedDict()
            if sensor[6] in sensors_group_domain[sensor[7]]:
                sensors_group_domain[sensor[7]][sensor[6]] += [sensor]
            else:
                sensors_group_domain[sensor[7]][sensor[6]] = [sensor]
    print("Metadata script [anode] sensor saved")
    return sensors_group_domain


def mode():
    mode = 'build'
    if len(sys.argv) == 2 and (sys.argv[1] == "clean" or sys.argv[1] == "build"):
        mode = sys.argv[1]
    return mode


if __name__ == "__main__":
    sensors = load()
