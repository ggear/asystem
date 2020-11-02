from __future__ import print_function

import os
import sys
import time
from datetime import datetime
from socket import gethostbyname

import pytz
from dateutil.parser import parse
from dns.resolver import Resolver
from requests import post
from speedtest import Speedtest

# TODO:
# - Test for all exceptions, wrong codes, pull ethernet, pull modem etc
# - Add InfluxDB logic (throughput echo or new)
# - Add unit tests against run codes, happy paths
# - Develop grafana graphs
# - Add a query to get public eth8 address
# - Add certifcate tests

DEFAULT_PROFILE_PATH = "../resources/config/.profile"
DEFAULT_INFLUXDB_HOST = "192.168.1.10"
DEFAULT_INFLUXDB_PORT = "8086"

HOST_HOME_NAME = "home.janeandgraham.com"

HOST_SPEEDTEST_PING_IDS = ["6359", "4153"]
HOST_SPEEDTEST_THROUGHPUT_IDS = ["2627", "30932", "7581"]

RESOLVER_IPS = ["192.168.1.1", "162.159.44.190", "1.1.1.1", "8.8.8.8"]

HOST_INTERNET_LOCATION = "darlington"
HOST_INTERNET_INTERFACE_ID = "udm-rack-eth8"

PING_COUNT = 3
PING_SLEEP_SECONDS = 1

RUN_CODE_SUCCESS = 0
RUN_CODE_FAIL_CONFIG = 1
RUN_CODE_FAIL_NETWORK = 2

FORMAT_PING = \
    "internet,metric=ping,host_id={},host_location={},host_name={} " \
    "ping_min_ms={},ping_max_ms={},ping_med_ms={},pings_lost={},run_code={},run_ms={} {}"
FORMAT_UPLOAD = \
    "internet,metric=upload,host_id={},host_location={},host_name={} " \
    "upload_mbps={},upload_bytes={},run_code={},run_ms={} {}"
FORMAT_DOWNLOAD = \
    "internet,metric=download,host_id={},host_location={},host_name={} " \
    "download_mbps={},download_bytes={},run_code={},run_ms={} {}"
FORMAT_LOOKUP = \
    "internet,metric=lookup,host_id={},host_location={},host_name={},resolver_ip={} " \
    "ip=\"{}\",run_code={},run_ms={} {}"
FORMAT_UPTIME = \
    "internet,metric=uptime,host_id={},host_location={},host_name={} " \
    "uptime_s={},metrics_suceeded={},metrics_failed={},run_code={},run_ms={} {}"

QUERY_UPTIME_LAST = """
from(bucket: "hosts")
  |> range(start: -1h, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "uptime")
  |> keep(columns: ["_value", "_time"])
  |> last()
"""


def load_profile(profile_file):
    profile = {}
    for profile_line in profile_file:
        profile_line = profile_line.replace("export ", "").rstrip()
        if "=" not in profile_line:
            continue
        if profile_line.startswith("#"):
            continue
        profile_key, profile_value = profile_line.split("=", 1)
        profile[profile_key] = profile_value
    profile["INFLUXDB_HOST"] = os.environ['INFLUXDB_HOST'] if "INFLUXDB_HOST" in os.environ else DEFAULT_INFLUXDB_HOST
    profile["INFLUXDB_PORT"] = os.environ['INFLUXDB_PORT'] if "INFLUXDB_PORT" in os.environ else DEFAULT_INFLUXDB_PORT
    return profile


def time_ms():
    return int(time.time() * 1000)


def time_ns():
    return int(time.time() * 1000000000)


def med(data):
    data.sort()
    mid = len(data) // 2
    return (data[mid] + data[~mid]) / 2


def query(env, flux):
    response = post(
        url="http://{}:{}/api/v2/query?org=home".format(env["INFLUXDB_HOST"], env["INFLUXDB_PORT"]),
        headers={
            'Accept': 'application/csv',
            'Content-type': 'application/vnd.flux',
            'Authorization': 'Token {}'.format(env["INFLUXDB_TOKEN"])
        }, data=flux)
    rows = []
    for row in response.content.strip().split("\n")[1:]:
        cols = row.split(",")
        rows.append([parse(cols[3])] + cols[4:])
    return rows


def ping():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS + HOST_SPEEDTEST_PING_IDS:
        pings = []
        host_speedtest = None
        time_start = time_ms()
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        for i in xrange(PING_COUNT):
            try:
                speedtest = Speedtest()
                speedtest.get_servers([host_speedtest_id])
                host_speedtest = speedtest.best
                speedtest_results = speedtest.results.dict()
                pings.append(speedtest_results["ping"])
                if i < PING_COUNT - 1:
                    time.sleep(PING_SLEEP_SECONDS)
                    time_start += PING_SLEEP_SECONDS * 1000
            except Exception as exception:
                print("Error processing speedtest ping [{}{}]"
                      .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
                run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (len(pings) > 0 and max(pings) > 0) else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_PING.format(
            "speedtest-" + host_speedtest_id,
            host_speedtest["name"].lower() if host_speedtest is not None else "",
            host_speedtest["host"].split(":")[0] if host_speedtest is not None else "",
            min(pings) if len(pings) > 0 else "",
            max(pings) if len(pings) > 0 else "",
            med(pings) if len(pings) > 0 else "",
            PING_COUNT - len(pings),
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def upload():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS:
        host_speedtest = None
        results_speedtest = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start = time_ms()
        try:
            speedtest = Speedtest()
            speedtest.get_servers([host_speedtest_id])
            host_speedtest = speedtest.best
            speedtest.upload()
            results_speedtest = speedtest.results.dict()
        except Exception as exception:
            print("Error processing speedtest upload [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
            run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "upload" in results_speedtest and results_speedtest["upload"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_UPLOAD.format(
            "speedtest-" + host_speedtest_id,
            host_speedtest["name"].lower() if host_speedtest is not None else "",
            host_speedtest["host"].split(":")[0] if host_speedtest is not None else "",
            results_speedtest["upload"] / 8000000 if results_speedtest is not None else "",
            results_speedtest["bytes_sent"] if results_speedtest is not None else "",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def download():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS:
        host_speedtest = None
        results_speedtest = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start = time_ms()
        try:
            speedtest = Speedtest()
            speedtest.get_servers([host_speedtest_id])
            host_speedtest = speedtest.best
            speedtest.download()
            results_speedtest = speedtest.results.dict()
        except Exception as exception:
            print("Error processing speedtest download [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
            run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "download" in results_speedtest and results_speedtest["download"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_DOWNLOAD.format(
            "speedtest-" + host_speedtest_id,
            host_speedtest["name"].lower() if host_speedtest is not None else "",
            host_speedtest["host"].split(":")[0] if host_speedtest is not None else "",
            results_speedtest["download"] / 8000000 if results_speedtest is not None else "",
            results_speedtest["bytes_received"] if results_speedtest is not None else "",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def lookup():
    run_responses = set()
    run_response_count = 0
    home_host_ip = None
    run_code_iteration = RUN_CODE_FAIL_NETWORK
    time_start = time_ms()
    try:
        home_host_ip = gethostbyname(HOST_HOME_NAME)
    except Exception as exception:
        print("Error processing DNS lookup [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
    if home_host_ip is not None and home_host_ip != "":
        run_code_iteration = RUN_CODE_SUCCESS
        run_response_count += 1
        run_responses.add(home_host_ip)
    print(FORMAT_LOOKUP.format(
        HOST_INTERNET_INTERFACE_ID,
        HOST_INTERNET_LOCATION,
        HOST_HOME_NAME,
        "127.0.0.1",
        home_host_ip if home_host_ip is not None else "",
        run_code_iteration,
        time_ms() - time_start,
        time_ns()))
    for home_host_resolver_ip in RESOLVER_IPS:
        home_host_response = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start = time_ms()
        try:
            home_host_resolver = Resolver()
            home_host_resolver.nameservers = [home_host_resolver_ip]
            home_host_responses = home_host_resolver.query(HOST_HOME_NAME, lifetime=2)
            if home_host_responses is not None and len(home_host_responses) == 1:
                home_host_response = home_host_responses[0]
        except Exception as exception:
            print("Error processing DNS lookup [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
        if home_host_response is not None and home_host_response.address is not None and home_host_response.address != "":
            run_code_iteration = RUN_CODE_SUCCESS
            run_response_count += 1
            run_responses.add(home_host_response.address)
        print(FORMAT_LOOKUP.format(
            HOST_INTERNET_INTERFACE_ID,
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            home_host_resolver_ip,
            home_host_response.address \
                if (home_host_response is not None and home_host_response.address is not None and home_host_response.address != "") else "",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return RUN_CODE_SUCCESS if (run_response_count == len(RESOLVER_IPS) + 1 and len(run_responses) == 1) else RUN_CODE_FAIL_NETWORK


if __name__ == "__main__":
    time_start_all = time_ms()
    profile_path = DEFAULT_PROFILE_PATH if len(sys.argv) == 1 else sys.argv[1]
    profile = None
    try:
        with open(profile_path, 'r') as profile_file:
            profile = load_profile(profile_file)
    except Exception as exception:
        print("Error processing profile [{}] [{}{}]"
              .format(profile_path, type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
    if profile is not None:
        run_code_all = []
        up_code = 0

        run_code_all.append(ping())
        up_code += run_code_all[-1]

        # TODO: Temporaliy disable upload/download speed tests
        # run_code_all.append(upload())
        # up_code += run_code_all[-1]
        # run_code_all.append(download())
        # up_code += run_code_all[-1]

        run_code_all.append(lookup())
        run_code_uptime = RUN_CODE_FAIL_CONFIG
        uptime_new = None
        uptime_epoch = None
        try:
            uptime_now = datetime.now(pytz.utc)
            uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
            uptime_rows = query(profile, QUERY_UPTIME_LAST)
            if len(uptime_rows) == 0 or up_code > 0:
                uptime_new = 0
            else:
                uptime_new = int((uptime_now - uptime_rows[0][0]).total_seconds()) + int(uptime_rows[0][1])
        except Exception as exception:
            print("Error processing uptime [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception), file=sys.stderr))
        if uptime_new is not None and uptime_epoch is not None:
            run_code_uptime = RUN_CODE_SUCCESS
        print(FORMAT_UPTIME.format(
            HOST_INTERNET_INTERFACE_ID,
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            uptime_new if uptime_new is not None else "",
            run_code_all.count(0) + (1 if run_code_uptime == RUN_CODE_SUCCESS else 0),
            len(run_code_all) - run_code_all.count(0) + (1 if run_code_uptime != RUN_CODE_SUCCESS else 0),
            run_code_uptime,
            time_ms() - time_start_all,
            uptime_epoch if uptime_epoch is not None else ""))
