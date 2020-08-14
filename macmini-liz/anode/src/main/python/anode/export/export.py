import inspect
import os
import sys

DIR_ROOT = os.path.dirname(os.path.realpath(__file__)) + "/../.."
DIR_WORK = DIR_ROOT + "/anode/export"
DIR_HOMEASSISTANT = DIR_WORK + "/../../../../../../../macmini-liz/homeassistant/src"
sys.path.insert(0, DIR_ROOT)

import json

import sys
import time
from anode.plugin.plugin import Plugin
import paho.mqtt.client as mqtt
import anode

MODE = "QUERY"

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
    os.path.join(DIR_ROOT, "../resources/config/anode.yaml"),
    os.path.join(DIR_ROOT, "../../../.env")
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
        if MODE == "DELETE":
            client.publish(topic, payload=None, qos=1, retain=True)
    except Exception as exception:
        print(exception)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        MODE = "DELETE"
    with open(DIR_WORK + "/sensors.csv", "r") as file:
        lines = iter(file.readlines())
        next(lines)
        for line in lines:
            sensor = line.strip().split(",")
            SENSORS[sensor[1]] = sensor

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # TODO: Implement localhost v production lookup
    client.connect('192.168.1.10', CONFIG["publish_port"], 60)

    time_start = time.time()
    while True:
        client.loop()
        time_elapsed = time.time() - time_start
        if time_elapsed > TIME_WAIT_SECS:
            client.disconnect()
            break

    sensors = sorted(SENSORS.values(), key=lambda x: x[0].zfill(7) + x[6] + x[8])
    with open(DIR_WORK + "/sensors.csv", "w") as file:
        for sensor in [SENSORS_HEADER] + sensors:
            file.write("{}\n".format(",".join(sensor)))

    with open(DIR_HOMEASSISTANT + "/customize.yaml", "w") as file:
        for sensor in sensors:
            file.write(inspect.cleandoc("""
                sensor.{}:
                  friendly_name: {}
            """.format(sensor[2], sensor[5])) + "\n")

    sensors_domain = {}
    for sensor in sensors:
        if sensor[6] in sensors_domain:
            sensors_domain[sensor[6]] += [sensor]
        else:
            sensors_domain[sensor[6]] = [sensor]
    with open(DIR_HOMEASSISTANT + "/lovelace.yaml", "w") as file:
        for domain in sensors_domain:
            file.write(
                "      - type: entities\n"
                "        show_header_toggle: false\n"
                "        entities:\n"
                    .format(domain))
            for sensor in sensors_domain[domain]:
                file.write(
                    "          - entity: sensor.{}\n"
                        .format(sensor[2]))

    print("{} [{}] metrics".format("DELETED" if MODE == "DELETE" else "DETECTED", len(SENSORS)))
