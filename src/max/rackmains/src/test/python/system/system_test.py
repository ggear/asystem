import json
import os
import random
import string
import subprocess
import sys
import time
from os.path import abspath, dirname, join, realpath

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.enums import CallbackAPIVersion

HOST = "127.0.0.1"
PORT = 32404
TIMEOUT = 10
TIMEOUT_WARMUP = 90
STATE_TOPIC = "rackmains/data"
STATUS_TOPIC = "rackmains/status"
SAMPLES = {
    "rackmains_battery_charge_pct": 100,
    "rackmains_battery_volts": 13.4,
    "rackmains_mains_input_volts": 241.4,
    "rackmains_mains_input_fault_volts": 241.4,
    "rackmains_output_hertz": 50.1,
    "rackmains_output_volts": 241.4,
    "rackmains_output_load_pct": 13,
}
STATUS_FILE = "/tmp/nutdrv_qx-powershield.status"
DIR_OUTAGE = "/asystem/mnt/outage"

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SCHEMA = join(DIR_ROOT, "src/build/resources/schema/vernemq")
SCHEMA_LEAF = "payload"


def test_publishes_readings():
    def test():
        received = {}

        def on_connect(client, _user_data, _flags, reason_code, _properties):
            client.subscribe(STATE_TOPIC, 1)
            client.subscribe(STATUS_TOPIC, 1)
            print(f"Connected [code={reason_code}]")

        def on_message(_client, _user_data, message):
            received[message.topic] = message.payload
            try:
                body = json.dumps(json.loads(message.payload), indent=2)
            except (ValueError, TypeError):
                body = message.payload.decode(errors="replace")
            print(f"Message [{message.topic}]\n{body}")

        client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id="".join(random.choice(string.ascii_lowercase) for _ in range(10)),
            clean_session=True,
        )
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(HOST, PORT)
        time_start = time.time()
        while ({STATE_TOPIC, STATUS_TOPIC} - received.keys()) and (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            pass
        client.disconnect()

        assert received.get(STATUS_TOPIC) == b"online"
        payload = json.loads(received[STATE_TOPIC])
        assert isinstance(payload["period_ms"], int)
        assert isinstance(payload["timestamp"], str) and len(payload["timestamp"]) == 20
        assert "samples" not in payload and "mains_status" not in payload
        assert payload["rackmains_ups_status"] == "OL"
        for key in ("rackmains_battery_low", "rackmains_battery_replace_due", "rackmains_ups_problem", "rackmains_ups_calibrating"):
            assert payload[key] == 0, key
        assert payload["rackmains_mains_present"] == 1
        assert payload["rackmains_read_failures"] == 0
        assert isinstance(payload["clock_epoch_seconds"], float)
        assert isinstance(payload["rackmains_battery_age_days"], int)
        assert payload["rackmains_guard_state"] == "idle" and payload["rackmains_guard_live"] == 0
        for key, value in SAMPLES.items():
            assert abs(payload[key] - value) < 0.001, key

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


def exec_in_container(*command):
    done = subprocess.run(["docker", "exec", "rackmains", *command], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return done.stdout


def health_status():
    done = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}", "rackmains"], capture_output=True, text=True, timeout=30)
    return done.stdout.strip()


def wait_until(check, timeout=TIMEOUT_WARMUP):
    time_start = time.time()
    while time.time() - time_start < timeout:
        value = check()
        if value:
            return value
        time.sleep(1)
    raise AssertionError(f"condition not met in {timeout}s")


def test_an_outage_is_recorded_and_the_service_stays_healthy_on_battery():
    exec_in_container("sh", "-c", f"echo 'OB DISCHRG' > {STATUS_FILE}")
    try:
        files = wait_until(lambda: exec_in_container("ls", DIR_OUTAGE).split())
        assert all(name.startswith("rackmains_outage_") and name.endswith(".csv") for name in files)
        rows = wait_until(lambda: exec_in_container("cat", join(DIR_OUTAGE, max(files))).splitlines())
        header = rows[0].split(",")
        assert header[:4] == ["time", "elapsed_seconds", "event", "detail"]
        assert "rackmains_mains_present" in header and "rackmains_guard_state" in header
        assert rows[1].split(",")[2] == "start"
        assert wait_until(lambda: health_status() == "healthy", 60)
    finally:
        exec_in_container("sh", "-c", f"echo OL > {STATUS_FILE}")


def test_declares_every_published_topic():
    declared = set(schema_topics())
    assert declared, f"no declared topics under [{DIR_SCHEMA}]"
    for topic in (STATE_TOPIC, STATUS_TOPIC):
        assert topic in declared, f"published topic [{topic}] is not declared"


def schema_topics():
    topics_dir = join(DIR_SCHEMA, "model")
    for directory, _, files in os.walk(topics_dir):
        if SCHEMA_LEAF in files:
            yield os.path.relpath(directory, topics_dir)


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
