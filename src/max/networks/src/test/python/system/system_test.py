import json
import random
import string
import sys
import time

import paho.mqtt.client as mqtt
import pytest

HOST = "127.0.0.1"
PORT = 32404
TIMEOUT = 15
TIMEOUT_WARMUP = 120
STATUS_TOPIC = "networks/status"
DATA_TOPIC = "networks/data/internet"
COMMAND_TOPIC = "networks/command/internet"
RESULT_TOPIC = "networks/command/result"
TRIAD = {"fit", "sick", "dead"}


def _client():
    return mqtt.Client("".join(random.choice(string.ascii_lowercase) for _ in range(10)), True)


def _assert_vitals(payload):
    body = json.loads(payload)
    assert isinstance(body["timestamp"], int)
    assert isinstance(body["ok"], bool)
    assert body["status"] in TRIAD
    assert isinstance(body["score"], int) and 0 <= body["score"] <= 100


def test_publishes_vitals_and_answers_command():
    def test():
        received = {}

        def on_connect(client, _user_data, _flags, return_code):
            client.subscribe(STATUS_TOPIC, 1)
            client.subscribe(DATA_TOPIC, 1)
            client.subscribe(RESULT_TOPIC, 1)
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
        client.publish(COMMAND_TOPIC, json.dumps({"command": "check"}), 1)
        time_start = time.time()
        while (RESULT_TOPIC not in received) and \
                (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            pass
        client.disconnect()
        _assert_vitals(received[RESULT_TOPIC])

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


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
