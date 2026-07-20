import json
import os
import random
import string
import sys
import time

import paho.mqtt.client as mqtt
import pytest

HOST = "127.0.0.1"
PORT = 32404
TIMEOUT = 10
TIMEOUT_WARMUP = 90
TEMPSTAT_HOST = os.environ.get("TEMPSTAT_HOST", "host.docker.internal")
STATE_TOPIC = "tempstat/{}/data".format(TEMPSTAT_HOST)
STATUS_TOPIC = "tempstat/{}/status".format(TEMPSTAT_HOST)
SENSORS = ["utility_temperature", "rack_top_temperature", "rack_bottom_temperature"]
CELSIUS = 25.0625


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
