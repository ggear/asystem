import os
import sys

DIR_ROOT = os.path.dirname(os.path.realpath(__file__)) + "/../../../.."
sys.path.insert(0, os.path.join(DIR_ROOT, "src/main/python"))

import os
import time
import paho.mqtt.client as mqtt
import requests
import anode
import pytest
import json
import websocket
import random
import string
import ssl
import urllib3

TIMEOUT = 2
TIMEOUT_WARMUP = 30

CONFIG = anode.anode.load_config(
    os.path.join(DIR_ROOT, "src/main/resources/config/anode.yaml"),
    os.path.join(DIR_ROOT, ".env")
)

urllib3.disable_warnings()


def get_metrics_sum():
    metrics_sum = 0
    for metric in requests.get("http://{}:{}/rest/?metrics=anode".format(CONFIG["host"], CONFIG["port"]), verify=False).json():
        if metric["data_metric"].endswith(".metrics"):
            metrics_sum += metric["data_value"]
    return metrics_sum


def test_warmup():
    def test():
        messages = []

        def on_connect(client, user_data, flags, return_code):
            client.connected = True

        def on_message(client, user_data, message):
            messages.append(message.payload)

        def on_disconnect(client, user_data, return_code):
            client.connected = False

        client = mqtt.Client("".join(random.choice(string.ascii_lowercase) for i in range(10)), True)
        client.connected = False
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(CONFIG["publish_host"], CONFIG["publish_port"])
        subscribed_messages = False
        time_start = time.time()
        while len(messages) < 1 and (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            if client.connected and not subscribed_messages:
                client.subscribe(CONFIG["publish_status_topic"], 1)
                subscribed_messages = True
        client.disconnect()
        assert len(messages) > 0
        assert messages[0] == "UP"

    # TODO: Speed this up, it takes 35 sec?

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


def test_http():
    metrics_sum = get_metrics_sum()

    def assert_get(query, len_min):
        response = requests.get("http://{}:{}/rest/?{}".format(CONFIG["host"], CONFIG["port"], query), verify=False)
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

    client = mqtt.Client("".join(random.choice(string.ascii_lowercase) for i in range(10)), True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(CONFIG["publish_host"], CONFIG["publish_port"], TIMEOUT)
    time_start = time.time()
    while (time.time() - time_start) < TIMEOUT and client.loop(2) == 0:
        pass
    client.disconnect()

    # TODO: Improve assertion
    assert len(metrics_metadata) > 0


def test_ws():
    metrics_sum = get_metrics_sum()

    def assert_receive(query, len_min):
        metrics_count = 0
        client = websocket.create_connection("ws://{}:{}/ws/?{}".format(CONFIG["host"], CONFIG["port"], query), sslopt={
            "cert_reqs": ssl.CERT_NONE, "check_hostname": False, "ssl_version": ssl.PROTOCOL_TLSv1})
        client.settimeout(TIMEOUT)
        while metrics_count < len_min:
            received = client.recv()
            metrics_count += 1
        client.close()
        assert metrics_count == len_min

    assert_receive("", metrics_sum)
    assert_receive("some=rubbish", metrics_sum)


def test_js():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../resources/karma"))
    assert os.system("karma start") == 0


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
