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

BROKER = "127.0.0.1"
TIMEOUT = 30
TIMEOUT_WARMUP = 180
TIMEOUT_RESTART = 90
SETTLE = 3
CONTAINER = "supervisor"
SCHEMA_LEAF = "payload"
ORPHAN = "zztest"
SERVICE = "zzservice"
BROKER_CONTAINER = "vernemq"
BARRIER_TOPICS = 550
BARRIER_ROUNDS = 3

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SCHEMA = join(DIR_ROOT, "src/build/resources/schema/vernemq")


def _env(name):
    with open(join(DIR_ROOT, ".env")) as env_file:
        value = ""
        for line in env_file:
            if line.startswith("{}=".format(name)):
                value = line.split("=", 1)[1].strip()
    assert value, "no [{}] in the generated .env".format(name)
    return value


HOST = _env("SUPERVISOR_HOST")
PORT = int(_env("BROKER_PORT"))
TOPIC_STATUS = "supervisor/{}/status".format(HOST)
TOPIC_PROCESSOR = "supervisor/{}/data/host/used_processor".format(HOST)
TOPIC_MEMORY = "supervisor/{}/data/host/used_memory".format(HOST)
TOPIC_SELF = "supervisor/{}/data/service/supervisor/name".format(HOST)
TOPIC_ORPHAN = "supervisor/{}/data/service/{}/name".format(HOST, ORPHAN)
TOPIC_TEMPERATURE = "supervisor/{}/data/host/temperature".format(HOST)
TOPIC_FAN = "supervisor/{}/data/host/spin_fan_speed".format(HOST)
TOPIC_LOGS = "supervisor/{}/data/host/failed_log_messages".format(HOST)
TOPIC_SHARES = "supervisor/{}/data/host/failed_shares".format(HOST)


def _configured():
    with open(join(DIR_ROOT, "src/main/resources/image/config.json")) as config_file:
        schema = json.load(config_file)["asystem"]["schema"]
    for entry in schema:
        if entry["host"] == HOST:
            return entry["services"]
    raise AssertionError("host [{}] is in no config.json schema entry".format(HOST))


def _client():
    client = mqtt.Client("".join(random.choice(string.ascii_lowercase) for _ in range(10)), True)
    client.connect(BROKER, PORT)
    return client


def _collect(topics, timeout):
    received = {}

    def on_connect(client, _user_data, _flags, return_code):
        for topic in topics:
            client.subscribe(topic, 1)
        print("Connected [code={}]".format(return_code))

    def on_message(_client, _user_data, message):
        if message.payload:
            received[message.topic] = message.payload
        elif message.topic in received:
            del received[message.topic]
        print("Message [{}] {}".format(message.topic, message.payload[:120]))

    client = _client()
    client.on_connect = on_connect
    client.on_message = on_message
    time_start = time.time()
    while (time.time() - time_start) < timeout and client.loop(1) == 0:
        pass
    client.disconnect()
    return received


def _await(topics, predicate, timeout, on_ready):
    received = {}
    matched = [False]

    def on_connect(client, _user_data, _flags, return_code):
        for topic in topics:
            client.subscribe(topic, 1)
        print("Connected [code={}]".format(return_code))
        on_ready(client)

    def on_message(_client, _user_data, message):
        received.setdefault(message.topic, []).append(message.payload)
        print("Message [{}] {}".format(message.topic, message.payload[:120]))
        if predicate(received):
            matched[0] = True

    client = _client()
    client.on_connect = on_connect
    client.on_message = on_message
    time_start = time.time()
    while not matched[0] and (time.time() - time_start) < timeout and client.loop(1) == 0:
        pass
    client.disconnect()
    return received, matched[0], time.time() - time_start


def _name_payload(name):
    detail = {"ok": True, "value": name}
    return json.dumps({"timestamp": int(time.time()), "pulse": detail, "trend": detail})


def _docker(*args):
    return subprocess.run(["docker"] + list(args), capture_output=True, text=True, check=False)


def _retry(assertion, timeout=TIMEOUT_WARMUP):
    failure = None
    time_start = time.time()
    while (time.time() - time_start) < timeout:
        try:
            assertion()
            return
        except Exception as exception:
            failure = exception
            print(exception)
            time.sleep(1)
    raise AssertionError("timed out after [{}] s with [{}]".format(int(time.time() - time_start), failure))


def test_publishes_vitals():
    def assertion():
        received = _collect([TOPIC_STATUS, TOPIC_PROCESSOR, TOPIC_MEMORY, TOPIC_SELF], SETTLE)
        missing = {TOPIC_STATUS, TOPIC_PROCESSOR, TOPIC_MEMORY, TOPIC_SELF} - received.keys()
        assert not missing, "topics not published [{}]".format(sorted(missing))
        assert received[TOPIC_STATUS] == b"online"
        for topic in (TOPIC_PROCESSOR, TOPIC_MEMORY):
            body = json.loads(received[topic])
            assert isinstance(body["timestamp"], int) and body["timestamp"] > 0
            assert isinstance(body["pulse"]["ok"], bool)
            assert 0 <= body["pulse"]["value"] <= 100
        assert json.loads(received[TOPIC_SELF])["pulse"]["value"] == CONTAINER

    _retry(assertion)


def test_reports_an_unmeasurable_metric_as_failed_and_an_absent_one_as_inert():
    def assertion():
        received = _collect([TOPIC_TEMPERATURE, TOPIC_FAN, TOPIC_LOGS], SETTLE)
        missing = {TOPIC_TEMPERATURE, TOPIC_FAN, TOPIC_LOGS} - received.keys()
        assert not missing, "topics not published [{}]".format(sorted(missing))
        temperature = json.loads(received[TOPIC_TEMPERATURE])
        assert temperature.get("failed") is True, "an unreadable sensor must carry failed, not a confident zero"
        for topic in (TOPIC_FAN, TOPIC_LOGS):
            body = json.loads(received[topic])
            assert not body.get("failed"), "[{}] has nothing to measure here, so it must not read failed".format(topic)
            assert body["pulse"]["ok"] is True, "[{}] must be inert and ok, not judged by a rule".format(topic)
            assert body["pulse"].get("value", 0) == 0

    _retry(assertion, TIMEOUT)


def test_logs_an_environment_fault_at_warn_and_a_host_fact_at_info():
    def assertion():
        lines = _docker("logs", CONTAINER).stdout.splitlines() + _docker("logs", CONTAINER).stderr.splitlines()
        warned = [line for line in lines if " WARN " in line and "host/temperature" in line]
        noted = [line for line in lines if " INFO " in line and "probe[sensors]" in line]
        assert warned, "an absent sensor is the environment, so it must log at WARN"
        assert noted, "the sensor tier is a permanent host fact, so it must log at INFO"
        assert not [line for line in lines if " ERROR " in line and "host/temperature" in line], \
            "an absent sensor is not a code fault, so it must not log at ERROR"

    _retry(assertion, TIMEOUT)


def test_reports_a_ghost_and_an_unconfigured_service():
    running = set(_docker("ps", "--format", "{{.Names}}").stdout.split())
    ghosts = sorted(set(_configured()) - running)
    assert ghosts, "no configured service is absent, so there is no ghost to assert"
    ghost = ghosts[0]
    topic_ghost = "supervisor/{}/data/service/{}/health_status".format(HOST, ghost)
    topic_ghost_name = "supervisor/{}/data/service/{}/name".format(HOST, ghost)
    topic_unconfigured = "supervisor/{}/data/service/vernemq/configured_status".format(HOST)

    def assertion():
        received = _collect([topic_ghost, topic_ghost_name, topic_unconfigured], SETTLE)
        assert topic_ghost_name in received, "a configured service with no container must still publish its name"
        ghost_health = json.loads(received[topic_ghost])
        assert ghost_health["pulse"]["ok"] is False, "a ghost must read not ok, never green"
        assert not ghost_health.get("failed"), "a ghost is measured, not unmeasurable, so it must not read failed"
        unconfigured = json.loads(received[topic_unconfigured])
        assert unconfigured["pulse"]["ok"] is False, "a running service absent from the config must read not ok"

    _retry(assertion, TIMEOUT)


def test_declares_every_published_topic():
    model_dir = join(DIR_SCHEMA, "model")
    declared = {os.path.relpath(directory, model_dir)
                for directory, _, files in os.walk(model_dir) if SCHEMA_LEAF in files}
    assert declared, "no declared topics under [{}]".format(DIR_SCHEMA)
    published = _collect(["supervisor/{}/#".format(HOST)], SETTLE * 4).keys()
    assert published, "nothing published to assert against"
    configured = set(_configured())
    undeclared = []
    for topic in published:
        tokens = topic.split("/")
        if len(tokens) > 4 and tokens[3] == "service" and tokens[4] not in configured:
            continue
        if topic not in declared:
            undeclared.append(topic)
    assert not undeclared, "published but not declared, run fab generate [{}]".format(sorted(undeclared))
    for topic in (TOPIC_STATUS, TOPIC_PROCESSOR, TOPIC_MEMORY, TOPIC_SELF):
        assert topic in declared, "published topic [{}] is not declared".format(topic)


def test_passes_its_own_health_check():
    def assertion():
        result = _docker("exec", CONTAINER, "/asystem/etc/checkexecuting.sh")
        assert result.returncode == 0, "checkexecuting exited [{}] [{}] [{}]".format(
            result.returncode, result.stdout.strip(), result.stderr.strip())

    _retry(assertion, TIMEOUT)


def test_never_panics_and_stays_healthy():
    def assertion():
        result = _docker("inspect", "--format", "{{.State.Health.Status}}", CONTAINER)
        assert result.stdout.strip() == "healthy", "container health [{}]".format(result.stdout.strip())
        logs = _docker("logs", CONTAINER)
        for stream in (logs.stdout, logs.stderr):
            assert "panic:" not in stream, "the service panicked"
            assert "goroutine " not in stream, "the service dumped a stack"

    _retry(assertion)


def test_reports_a_declared_share_that_never_mounts_as_failed():
    def assertion():
        received = _collect([TOPIC_SHARES], SETTLE)
        assert TOPIC_SHARES in received, "failed shares must be published"
        body = json.loads(received[TOPIC_SHARES])
        assert not body.get("failed"), "a share declared and absent is countable, so the metric measured it"
        assert body["pulse"]["value"] == 100, "the fixture declares one share and mounts none"
        assert body["pulse"]["ok"] is False, "a failed share must read not ok, which is the only red the fixture drives"

    _retry(assertion)


def test_registers_a_service_that_appears_and_removes_one_that_goes():
    topic = "supervisor/{}/data/service/{}/name".format(HOST, SERVICE)
    image = "supervisor:{}".format(_env("SERVICE_VERSION_ABSOLUTE"))
    _docker("rm", "-f", SERVICE)
    assert _collect([topic], SETTLE) == {}, "the service topic is not clear before the test"
    _, appeared, elapsed = _await(
        [topic],
        lambda seen: seen[topic][-1] != b"",
        TIMEOUT,
        lambda _client: _docker("run", "-d", "--name", SERVICE, image, "sleep", "600"))
    assert appeared, "a container that appears must be published within [{}] s".format(int(elapsed))
    received, departed, _ = _await(
        [topic],
        lambda seen: len(seen[topic]) >= 3 and seen[topic][-1] == b"",
        TIMEOUT,
        lambda _client: _docker("rm", "-f", SERVICE))
    payloads = received.get(topic, [])
    assert departed, "a container that goes must be tombstoned, saw [{}]".format(payloads)
    assert json.loads(payloads[-2]).get("pulse") is None, "the form before the empty payload carries no pulse"
    assert _collect([topic], SETTLE) == {}, "the retained service topic must end cleared"


def test_resumes_publishing_after_the_broker_restarts():
    published_before = int(time.time())
    assert _docker("restart", BROKER_CONTAINER).returncode == 0

    def assertion():
        received = _collect([TOPIC_STATUS, TOPIC_PROCESSOR], SETTLE)
        assert received.get(TOPIC_STATUS) == b"online", "the host must re-assert online after a broker restart"
        body = json.loads(received[TOPIC_PROCESSOR])
        assert body["timestamp"] >= published_before, "a stale retained value proves nothing, the host must publish again"

    _retry(assertion, TIMEOUT_RESTART)


def test_removes_a_service_that_departs():
    assert _collect([TOPIC_ORPHAN], SETTLE) == {}, "the orphan topic is not clear before the test"
    received, matched, elapsed = _await(
        [TOPIC_ORPHAN],
        lambda seen: len(seen[TOPIC_ORPHAN]) >= 3 and seen[TOPIC_ORPHAN][-1] == b"",
        TIMEOUT,
        lambda client: client.publish(TOPIC_ORPHAN, _name_payload(ORPHAN), 1, True))
    payloads = received.get(TOPIC_ORPHAN, [])
    assert matched, "orphan not tombstoned within [{}] s, saw [{}]".format(int(elapsed), payloads)
    assert payloads[-1] == b"", "the last form must be the empty payload"
    departing = json.loads(payloads[-2])
    assert departing.get("pulse") is None, "the form before it must carry no pulse"
    assert departing["timestamp"] > 0, "the nil form must carry a stamp, which is what proves the host alive"
    assert _collect([TOPIC_ORPHAN], SETTLE) == {}, "the retained orphan topic must end cleared"


def test_retains_its_records_across_a_graceful_stop():
    assert _docker("stop", CONTAINER).returncode == 0
    time.sleep(SETTLE)
    received = _collect([TOPIC_STATUS, TOPIC_PROCESSOR, TOPIC_MEMORY, TOPIC_SELF], SETTLE)
    assert received.get(TOPIC_STATUS) == b"offline", "the offline status must be published"
    for topic in (TOPIC_PROCESSOR, TOPIC_MEMORY, TOPIC_SELF):
        assert topic in received, "retained [{}] must survive a graceful stop".format(topic)


def test_rediscovers_and_clears_an_orphan_on_restart():
    planter = _client()
    planter.loop_start()
    planter.publish(TOPIC_ORPHAN, _name_payload(ORPHAN), 1, True).wait_for_publish()
    planter.loop_stop()
    planter.disconnect()
    assert _collect([TOPIC_ORPHAN], SETTLE), "the orphan must be retained while the host is down"
    started = [False]

    def start_container(_client):
        if not started[0]:
            started[0] = True
            assert _docker("start", CONTAINER).returncode == 0

    received, matched, elapsed = _await(
        [TOPIC_ORPHAN, TOPIC_PROCESSOR],
        lambda seen: seen.get(TOPIC_ORPHAN, [b"x"])[-1] == b"",
        TIMEOUT_RESTART,
        start_container)
    assert matched, "the orphan must be tombstoned after a restart, saw [{}]".format(received)
    print("Cleared the orphan [{}] s after the restart".format(round(elapsed, 1)))
    assert _collect([TOPIC_ORPHAN], SETTLE) == {}, "the retained orphan topic must end cleared"


def test_publishes_its_will_and_keeps_its_records_when_killed():
    assert _docker("kill", CONTAINER).returncode == 0

    def assertion():
        received = _collect([TOPIC_STATUS, TOPIC_PROCESSOR, TOPIC_SELF], SETTLE)
        assert received.get(TOPIC_STATUS) == b"offline", "the last will must mark a killed host offline"
        for topic in (TOPIC_PROCESSOR, TOPIC_SELF):
            assert topic in received, "a kill publishes nothing, so retained [{}] must survive".format(topic)

    _retry(assertion, TIMEOUT_RESTART)
    assert _docker("start", CONTAINER).returncode == 0


def test_retained_delivery_precedes_a_barrier_published_after_the_subscribe():
    prefix = "zztest/barrier"
    data = "{}/data".format(prefix)
    nonce_topic = "{}/nonce".format(prefix)
    seeder = _client()
    seeder.loop_start()
    for index in range(BARRIER_TOPICS):
        seeder.publish("{}/{}".format(data, index), str(index), 0, True)
    seeder.publish("{}/{}".format(data, BARRIER_TOPICS - 1), str(BARRIER_TOPICS - 1), 1, True).wait_for_publish()
    seeder.loop_stop()
    seeder.disconnect()
    def barrier_round():
        order = []

        def on_connect(client, _user_data, _flags, _return_code):
            client.subscribe([(data + "/#", 0), (nonce_topic, 0)])
            client.publish(nonce_topic, "barrier", 0, False)

        def on_message(_client, _user_data, message):
            order.append(message.topic)

        client = _client()
        client.on_connect = on_connect
        client.on_message = on_message
        time_start = time.time()
        while nonce_topic not in order and (time.time() - time_start) < TIMEOUT and client.loop(1) == 0:
            pass
        client.disconnect()
        return order

    try:
        for round_index in range(BARRIER_ROUNDS):
            order = barrier_round()
            assert nonce_topic in order, "the barrier never returned in round [{}]".format(round_index)
            before = order.index(nonce_topic)
            assert before == BARRIER_TOPICS, \
                "round [{}] saw [{}] of [{}] retained topics before the barrier, so ordering does not hold".format(
                    round_index, before, BARRIER_TOPICS)
    finally:
        cleaner = _client()
        cleaner.loop_start()
        for index in range(BARRIER_TOPICS):
            cleaner.publish("{}/{}".format(data, index), None, 0, True)
        cleaner.publish("{}/{}".format(data, BARRIER_TOPICS - 1), None, 1, True).wait_for_publish()
        cleaner.loop_stop()
        cleaner.disconnect()


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
