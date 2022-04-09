import sys

sys.path.append('../../../main/python')

import os
import glob
import shutil
import pytest
from wrangle.core.plugin import library
from requests import post
import time
import subprocess
from tabulate import tabulate

TIMEOUT_WARMUP = 30

for key, value in list(library.load_profile(library.get_file(".env")).items()):
    os.environ[key] = value


def test_warmup():
    print("")
    dir_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../src/test/resources/data")
    dir_runtime = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../target/runtime-system/data")
    shutil.rmtree(dir_runtime, ignore_errors=True)
    os.makedirs(dir_runtime)
    for dir_typical in glob.glob("{}/*/success_typical".format(dir_test)):
        shutil.copytree(dir_typical, os.path.join(dir_runtime, os.path.basename(os.path.dirname(dir_typical))))
    success = False
    time_start_warmup = time.time()
    while not success and (time.time() - time_start_warmup) < TIMEOUT_WARMUP:
        try:
            success = query("""
from(bucket: "data_public")
  |> range(start: -10ms, stop: now()) 
  |> filter(fn: (r) => r._measurement == "a_non_existent_metric")
""") is not None
        except Exception as exception:
            print(exception)
            print("Waiting for influxdb server to come up ...")
            time.sleep(1)
    assert success is True


def test_typical():
    data_public_len = bucket_length("data_public")
    data_private_len = bucket_length("data_private")
    process = subprocess.Popen("docker exec wrangle telegraf --debug --once",
                               shell=True, stdout=subprocess.PIPE)
    process.wait()
    assert process.returncode == 0
    assert bucket_length("data_public") > data_public_len
    assert bucket_length("data_private") > data_private_len


def test_noop():
    data_public_len = bucket_length("data_public")
    data_private_len = bucket_length("data_private")
    process = subprocess.Popen("docker exec wrangle telegraf --debug --once",
                               shell=True, stdout=subprocess.PIPE)
    process.wait()
    assert process.returncode == 0
    assert bucket_length("data_public") >= data_public_len
    assert bucket_length("data_private") >= data_private_len


def test_reload():
    data_public_len = bucket_length("data_public")
    data_private_len = bucket_length("data_private")
    process = subprocess.Popen("docker exec -e WRANGLE_REPROCESS_ALL_FILES=true wrangle telegraf --debug --once",
                               shell=True, stdout=subprocess.PIPE)
    process.wait()
    assert process.returncode == 0
    assert bucket_length("data_public") > data_public_len
    assert bucket_length("data_private") > data_private_len


def bucket_length(bucket):
    rows = query("""
from(bucket: "{}")
  |> range(start: -20y, stop: now())
  |> group()
  |> count()
""".format(bucket))
    length = 0
    if rows is not None and len(rows) > 0 and len(rows[0]) > 0:
        length = int(rows[0][0])
    print("Bucket [{}] length [{}]".format(bucket, length))
    return length


def query(flux):
    target = "http://{}:{}/api/v2/query?org={}".format(os.environ["INFLUXDB_IP"], os.environ["INFLUXDB_PORT"], os.environ["INFLUXDB_ORG"])
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
