import random
import string
import sys
import time

import paho.mqtt.client as mqtt
import pytest

HOST = "127.0.0.1"
PORT = 1883
COUNT = 10
TIMEOUT = 2
TIMEOUT_WARMUP = 30
TOPIC = "{}/dev/test".format("".join(random.choice(string.ascii_lowercase) for i in range(10)))


def test_pubsub():
    def test():
        messages = []

        def on_connect(client, user_data, flags, return_code):
            client.connected = True
            print("CONNECTION [{}]".format(return_code))

        def on_message(client, user_data, message):
            messages.append(message.payload)
            print("RECEIVED MESSAGE [{}]".format(message.payload))

        def on_disconnect(client, user_data, return_code):
            client.connected = False
            print("DISCONNECTED [{}]".format(return_code))

        client = mqtt.Client("".join(random.choice(string.ascii_lowercase) for i in range(10)), True)
        client.connected = False
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(HOST, PORT)
        sent_messages = False
        subscribed_messages = False
        time_start = time.time()
        while len(messages) < COUNT and (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            if client.connected and not sent_messages:
                for i in range(COUNT):
                    client.publish("{}/{}".format(TOPIC, i), "Test {}".format(i), 1, True)
                sent_messages = True
            elif client.connected and not subscribed_messages:
                client.subscribe("{}/#".format(TOPIC), 1)
                subscribed_messages = True
        client.disconnect()
        print("MESSAGES [{}]".format(len(messages)))
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


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
