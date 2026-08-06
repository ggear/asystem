import json
import os
import random
import string
import subprocess
import sys
import time
from os.path import abspath, dirname, isfile, join, realpath

import paho.mqtt.client as mqtt
import pytest

HOST = "127.0.0.1"
PORT = 32404
TIMEOUT = 10
TIMEOUT_WARMUP = 90
STATE_TOPIC = "tempstat/data"
STATUS_TOPIC = "tempstat/status"
SENSORS = ["utility_temperature", "rack_top_temperature", "rack_bottom_temperature"]
CELSIUS = 25.0625

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SCHEMA = join(DIR_ROOT, "src/build/resources/schema/vernemq")


def test_publishes_readings():
    def test():
        received = {}

        def on_connect(client, _user_data, _flags, return_code):
            client.subscribe(STATE_TOPIC, 1)
            client.subscribe(STATUS_TOPIC, 1)
            print("Connected [code={}]".format(return_code))

        def on_message(_client, _user_data, message):
            received[message.topic] = message.payload
            try:
                body = json.dumps(json.loads(message.payload), indent=2)
            except (ValueError, TypeError):
                body = message.payload.decode(errors="replace")
            print("Message [{}]\n{}".format(message.topic, body))

        client = mqtt.Client("".join(random.choice(string.ascii_lowercase) for _ in range(10)), True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(HOST, PORT)
        time_start = time.time()
        while ({STATE_TOPIC, STATUS_TOPIC} - received.keys()) and \
                (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            pass
        client.disconnect()

        assert received.get(STATUS_TOPIC) == b"online"
        payload = json.loads(received[STATE_TOPIC])
        assert isinstance(payload["period_ms"], int)
        assert isinstance(payload["timestamp"], str) and len(payload["timestamp"]) == 20
        for sensor in SENSORS:
            assert abs(payload["samples"]["{}_celsius".format(sensor)] - CELSIUS) < 0.001
        for topic, retained in received.items():
            assert_declared_shape(topic, retained)

    success = False
    time_start_warmup = time.time()
    while not success and (time.time() - time_start_warmup) < TIMEOUT_WARMUP:
        try:
            test()
            success = True
        except Exception as exception:
            print(exception)
            time.sleep(1)
    assert success is True


def test_declares_every_published_topic():
    declared = set(schema_topics())
    assert declared, "no declared topics under [{}]".format(DIR_SCHEMA)
    for topic in (STATE_TOPIC, STATUS_TOPIC):
        assert topic in declared, "published topic [{}] is not declared".format(topic)


def schema_topics():
    topics_dir = join(DIR_SCHEMA, "topics")
    for directory, _, files in os.walk(topics_dir):
        for name in files:
            yield os.path.relpath(join(directory, name), topics_dir)


def assert_declared_shape(topic, retained):
    filter_path = join(DIR_SCHEMA, "filters", topic)
    values_path = join(DIR_SCHEMA, "values", topic)
    if isfile(filter_path):
        completed = subprocess.run(["jq", "-e", "-f", filter_path], input=retained,
                                   capture_output=True, check=False)
        assert completed.returncode == 0, \
            "retained payload on [{}] does not match its declared shape [{}]".format(topic, retained)
    elif isfile(values_path):
        with open(values_path) as values_file:
            allowed = {line.strip() for line in values_file if line.strip()}
        assert retained.decode().strip() in allowed, \
            "retained payload on [{}] is not a declared value [{}]".format(topic, retained)


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
