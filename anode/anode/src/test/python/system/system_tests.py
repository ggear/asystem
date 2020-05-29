import os
import sys

DIR_ROOT = os.path.dirname(os.path.realpath(__file__)) + "/../../../.."
sys.path.insert(0, os.path.join(DIR_ROOT, "src/main/python"))

import os

import requests
import pytest
import anode
import json
import time
import sys
import paho.mqtt.client as mqtt
import websocket

HOST = "localhost"

TIME_WAIT_SECS = 1

CONFIG = anode.anode.load_config(
    os.path.join(DIR_ROOT, "src/main/resources/config/anode.yaml"),
    os.path.join(DIR_ROOT, "src/main/resources/config/.profile"))


def get_metrics_sum():
    metrics_sum = 0
    for metric in requests.get("http://{}:{}/rest/?metrics=anode".format(HOST, CONFIG["port"])).json():
        if metric["data_metric"].endswith(".metrics"):
            metrics_sum += metric["data_value"]
    return metrics_sum


def test_http():
    metrics_sum = get_metrics_sum()

    def assert_get(query, len_min):
        response = requests.get("http://{}:{}/rest/?{}".format(HOST, CONFIG["port"], query))
        assert response is not None
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()) >= len_min
        return len(response.json())

    assert_get("", metrics_sum)
    assert_get("some=rubbish", metrics_sum)


def test_mqtt():
    metrics_metadata = []

    def on_connect(client, user_data, flags, return_code):
        client.subscribe("dev/{}/#".format(CONFIG["publish_push_metadata_topic"]))

    def on_message(client, user_data, message):
        if len(message.payload) > 0:
            metrics_metadata.append(json.loads(message.payload.decode("unicode-escape").encode("utf-8")))

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(CONFIG["publish_host"], CONFIG["publish_port"], 60)
    time_start = time.time()
    while True:
        client.loop()
        time_elapsed = time.time() - time_start
        if time_elapsed > TIME_WAIT_SECS:
            client.disconnect()
            break
    assert len(metrics_metadata) > 0


def test_ws():
    metrics_sum = get_metrics_sum()

    def assert_receive(query, len_min):
        metrics_count = 0
        client = websocket.create_connection("ws://{}:{}/ws/?{}".format(HOST, CONFIG["port"], query))
        client.settimeout(TIME_WAIT_SECS)
        while metrics_count < len_min:
            received = client.recv()
            metrics_count += 1
        client.close()
        assert metrics_count == len_min

    assert_receive("", metrics_sum)
    assert_receive("some=rubbish", metrics_sum)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-v", "--durations=50", "-o", "cache_dir=../target/.pytest_cache"])
    sys.exit(pytest.main())
