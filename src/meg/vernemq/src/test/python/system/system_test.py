import random
import string
import sys
import time
from os.path import abspath, dirname, join, realpath

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.enums import CallbackAPIVersion

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
HOST = "127.0.0.1"
PORT = 32404
COUNT = 10
TIMEOUT = 2
TIMEOUT_WARMUP = 30
TOPIC = "{}/dev/test".format("".join(random.choice(string.ascii_lowercase) for i in range(10)))


def test_pubsub():
    def test():
        messages = []
        connected = False

        def on_connect(client, user_data, flags, reason_code, properties):
            nonlocal connected
            connected = True
            print(f"CONNECTION [{reason_code}]")

        def on_message(client, user_data, message):
            messages.append(message.payload)
            print(f"RECEIVED MESSAGE [{message.payload}]")

        def on_disconnect(client, user_data, flags, reason_code, properties):
            nonlocal connected
            connected = False
            print(f"DISCONNECTED [{reason_code}]")

        client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="".join(random.choice(string.ascii_lowercase) for i in range(10)), clean_session=True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(HOST, PORT)
        sent_messages = False
        subscribed_messages = False
        time_start = time.time()
        while len(messages) < COUNT and (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            if connected and not sent_messages:
                for i in range(COUNT):
                    client.publish(f"{TOPIC}/{i}", f"Test {i}", 1, True)
                sent_messages = True
            elif connected and not subscribed_messages:
                client.subscribe(f"{TOPIC}/#", 1)
                subscribed_messages = True
        client.disconnect()
        print(f"MESSAGES [{len(messages)}]")
        assert len(messages) == COUNT

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


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )
