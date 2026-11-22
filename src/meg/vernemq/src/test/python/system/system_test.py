import random
import string
import subprocess
import sys
import threading
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
TIMEOUT_RESTART = 120
CONTAINER = "vernemq"
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


def test_pubsub_from_boot():
    def connect(name, on_message=None):
        client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"{name}-{''.join(random.choice(string.ascii_lowercase) for i in range(10))}", clean_session=True)
        if on_message is not None:
            client.on_message = on_message
        acknowledged = threading.Event()
        dropped = threading.Event()
        client.on_connect = lambda client, user_data, flags, reason_code, properties: acknowledged.set() if not reason_code.is_failure else dropped.set()
        client.on_disconnect = lambda client, user_data, flags, reason_code, properties: dropped.set()
        time_start = time.time()
        while (time.time() - time_start) < TIMEOUT_RESTART:
            dropped.clear()
            try:
                client.connect(HOST, PORT)
            except OSError:
                time.sleep(0.05)
                continue
            client.loop_start()
            time_attempt = time.time()
            while not acknowledged.is_set() and not dropped.is_set() and (time.time() - time_attempt) < TIMEOUT:
                time.sleep(0.01)
            if acknowledged.is_set():
                return client
            client.loop_stop()
            client.disconnect()
            time.sleep(0.05)
        raise AssertionError(f"broker not acknowledging connections after [{TIMEOUT_RESTART}] seconds")

    restarted = subprocess.run(["docker", "restart", "-t", "0", CONTAINER], capture_output=True, text=True, timeout=TIMEOUT_RESTART, check=False)
    assert restarted.returncode == 0, restarted.stderr
    topic = f"{TOPIC}/boot"
    received = {index: [] for index in range(COUNT)}
    subscribers = {}

    def subscribe(index):
        time.sleep(index * TIMEOUT / COUNT)
        subscribers[index] = connect(f"subscriber{index}", lambda client, user_data, message: received[index].append(message.payload))
        subscribers[index].subscribe(topic, 1)

    threads = [threading.Thread(target=subscribe, args=(index,)) for index in range(COUNT)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    publisher = connect("publisher")
    for i in range(COUNT):
        publisher.publish(topic, f"Live {i}", 1, False)
        time.sleep(TIMEOUT / COUNT)
    time_start = time.time()
    while any(len(messages) < COUNT for messages in received.values()) and (time.time() - time_start) < TIMEOUT:
        time.sleep(0.1)
    for client in [publisher, *subscribers.values()]:
        client.loop_stop()
        client.disconnect()
    counts = sorted(len(messages) for messages in received.values())
    print(f"MESSAGES PER SUBSCRIBER {counts}")
    assert counts == [COUNT] * COUNT


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
