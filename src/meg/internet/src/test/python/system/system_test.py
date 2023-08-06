import os
import subprocess
import sys
import time

import pytest
from requests import post
from tabulate import tabulate

sys.path.append('../../../main/python')

TIMEOUT_WARMUP = 30

with open(abspath("{}/../../../../.env".format(dirname(realpath(__file__)))), 'r') as profile_file:
    for profile_line in profile_file:
        if "=" in profile_line and not profile_line.startswith("#"):
            os.environ[profile_line.strip().split("=", 1)[0]] = profile_line.strip().split("=", 1)[1]


def test_warmup():
    print("")
    success = False
    time_start_warmup = time.time()
    while not success and (time.time() - time_start_warmup) < TIMEOUT_WARMUP:
        try:
            success = query("""
from(bucket: "host_private")
  |> range(start: -10ms, stop: now())
  |> filter(fn: (r) => r._measurement == "a_non_existent_metric")
""") is not None
        except Exception as exception:
            print(exception)
            print("Waiting for influxdb server to come up ...")
            time.sleep(1)
    assert success is True


def test_first_run():
    process = subprocess.Popen("docker exec internet telegraf --debug --once", shell=True, stdout=subprocess.PIPE)
    process.wait()
    assert process.returncode == 0
    assert measurement_length("host_private", "internet") >= 33


def test_second_run():
    process = subprocess.Popen("docker exec internet telegraf --debug --once", shell=True, stdout=subprocess.PIPE)
    process.wait()
    assert process.returncode == 0
    assert measurement_length("host_private", "internet") >= 64


def measurement_length(bucket, measurement):
    rows = query("""
from(bucket: "{}")
  |> range(start: -20y, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "{}")
  |> group()
  |> count()
""".format(bucket, measurement))
    length = 0
    if rows is not None and len(rows) > 0 and len(rows[0]) > 0:
        length = int(rows[0][0])
    print("Bucket [{}] measurement [{}] length [{}]".format(bucket, measurement, length))
    return length


def query(flux):
    target = "http://{}:{}/api/v2/query?org={}" \
        .format(os.environ["INFLUXDB_IP"], os.environ["INFLUXDB_HTTP_PORT"], os.environ["INFLUXDB_ORG"])
    response = post(url=target, headers={
        'Accept': 'application/csv',
        'Content-type': 'application/vnd.flux',
        'Authorization': 'Token {}'.format(os.environ["INFLUXDB_TOKEN"])
    }, data=flux)
    if response.status_code != 200:
        raise Exception("Query failed:{}with server [{}] and error code [{}]".format(flux, target, response.status_code))
    rows = []
    for row in response.text.strip().split("\n")[1:]:
        cols = row.strip().split(",")
        if len(cols) > 5:
            rows.append(cols[5:])
    print("Executed query:{}with server [{}], status code [{}] and response:\n{}"
          .format(flux, target, response.status_code, tabulate(rows, tablefmt="grid")))
    return rows


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
