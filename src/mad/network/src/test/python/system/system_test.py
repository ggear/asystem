import json
import os
import random
import string
import sys
import time
from os.path import abspath, dirname, join, realpath

import paho.mqtt.client as mqtt
import pytest

HOST = "127.0.0.1"
PORT = 32404
TIMEOUT = 15
TIMEOUT_WARMUP = 120
SETTLE = 3
STATUS_TOPIC = "network/status"
DATA_TOPIC = "network/data/internet"
COMMAND_TOPIC = "network/command/internet"
TRIAD = {"fit", "sick", "dead"}

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SCHEMA = join(DIR_ROOT, "src/build/resources/schema/vernemq")
SCHEMA_LEAF = "payload"


def _client():
    return mqtt.Client("".join(random.choice(string.ascii_lowercase) for _ in range(10)), True)


def _assert_vitals(payload):
    body = json.loads(payload)
    assert isinstance(body["timestamp"], int)
    assert isinstance(body["ok"], bool)
    assert body["status"] in TRIAD
    assert isinstance(body["score"], int) and 0 <= body["score"] <= 100


def test_publishes_vitals_and_accepts_switch_command():
    def test():
        received = {}

        def on_connect(client, _user_data, _flags, return_code):
            client.subscribe(STATUS_TOPIC, 1)
            client.subscribe(DATA_TOPIC, 1)
            print("Connected [code={}]".format(return_code))

        def on_message(_client, _user_data, message):
            received[message.topic] = message.payload
            print("Message [{}] {}".format(message.topic, message.payload))

        client = _client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(HOST, PORT)
        time_start = time.time()
        while ({STATUS_TOPIC, DATA_TOPIC} - received.keys()) and \
                (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            pass
        assert received.get(STATUS_TOPIC) == b"online"
        _assert_vitals(received[DATA_TOPIC])
        client.publish(COMMAND_TOPIC, "OFF", 1)
        client.publish(COMMAND_TOPIC, "ON", 1)
        time_start = time.time()
        while (time.time() - time_start) < SETTLE and client.loop(1) == 0:
            pass
        client.disconnect()
        assert received.get(STATUS_TOPIC) == b"online"
        _assert_vitals(received[DATA_TOPIC])

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
    declared = set(_schema_topics())
    assert declared, "no declared topics under [{}]".format(DIR_SCHEMA)
    for topic in (STATUS_TOPIC, DATA_TOPIC, COMMAND_TOPIC):
        assert topic in declared, "published topic [{}] is not declared".format(topic)


def _schema_topics():
    topics_dir = join(DIR_SCHEMA, "model")
    for directory, _, files in os.walk(topics_dir):
        if SCHEMA_LEAF in files:
            yield os.path.relpath(directory, topics_dir)


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
