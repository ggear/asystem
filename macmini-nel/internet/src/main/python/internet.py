from __future__ import print_function

import datetime
import os
import socket
import ssl
import sys
import time
from datetime import datetime
from socket import gethostbyname

import pytz
from dateutil.parser import parse
from dns.resolver import Resolver
from requests import post
from speedtest import Speedtest

DEFAULT_PROFILE_PATH = "../resources/config/.profile"
DEFAULT_INFLUXDB_HOST = "192.168.1.10"
DEFAULT_INFLUXDB_PORT = "8086"

HOST_HOME_NAME = "home.janeandgraham.com"

HOST_SPEEDTEST_PING_IDS = ["30932", "7581"]
HOST_SPEEDTEST_THROUGHPUT_IDS = ["2627"]

RESOLVER_IPS = ["192.168.1.1", "162.159.44.190", "1.1.1.1", "8.8.8.8"]

HOST_INTERNET_LOCATION = "darlington"
HOST_INTERNET_INTERFACE_ID = "udm-rack-eth8"

PING_COUNT = 3
PING_SLEEP_SECONDS = 1
SERVICE_TIMEOUT_SECONDS = 2

RUN_CODE_SUCCESS = 0
RUN_CODE_FAIL_CONFIG = 1
RUN_CODE_FAIL_NETWORK = 2

DATE_TLS = r'%b %d %H:%M:%S %Y %Z'

FORMAT_TEMPLATE = "internet,metric={},host_id={}{}run_code={},run_ms={} {}"

QUERY_IP = """
from(bucket: "hosts")
  |> range(start: -2h, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_value", "_time"])
  |> last()
"""

QUERY_UPTIME = """
from(bucket: "hosts")
  |> range(start: -2h, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "{}")
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


def ping(env):
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
                      .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
                run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (len(pings) > 0 and max(pings) > 0) else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "ping",
            "speedtest-" + host_speedtest_id,
            "{} ping_min_ms={},ping_max_ms={},ping_med_ms={},pings_lost={},".format(
                ",host_location={},host_name={}".format(
                    host_speedtest["name"].lower(),
                    host_speedtest["host"].split(":")[0]
                ) if host_speedtest is not None else "",
                min(pings),
                max(pings),
                med(pings),
                PING_COUNT - len(pings)
            ) if len(pings) > 0 else " ",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def upload(env):
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
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
            run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "upload" in results_speedtest and results_speedtest["upload"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "upload",
            "speedtest-" + host_speedtest_id,
            "{} upload_mbps={},upload_bytes={},".format(
                ",host_location={},host_name={}".format(
                    host_speedtest["name"].lower(),
                    host_speedtest["host"].split(":")[0]
                ) if host_speedtest is not None else "",
                results_speedtest["upload"] / 8000000,
                results_speedtest["bytes_sent"]
            ) if results_speedtest is not None else " ",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def download(env):
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
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
            run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "download" in results_speedtest and results_speedtest["download"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "download",
            "speedtest-" + host_speedtest_id,
            "{} download_mbps={},download_bytes={},".format(
                ",host_location={},host_name={}".format(
                    host_speedtest["name"].lower(),
                    host_speedtest["host"].split(":")[0]
                ) if host_speedtest is not None else "",
                results_speedtest["download"] / 8000000,
                results_speedtest["bytes_received"]
            ) if results_speedtest is not None else " ",
            run_code_iteration,
            time_ms() - time_start,
            time_ns()))
    return run_code


def lookup(env):
    time_start = time_ms()
    run_replies = set()
    run_reply_count = 0
    home_host_ip = None
    run_code_iteration = RUN_CODE_FAIL_NETWORK
    time_start_iteration = time_ms()
    try:
        home_host_ip = query(env, QUERY_IP)
    except Exception as exception:
        print("Error processing DNS lookup [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
    if home_host_ip is not None and len(home_host_ip) > 0 and len(home_host_ip[0]) > 1 and home_host_ip[0][1] != "":
        run_code_iteration = RUN_CODE_SUCCESS
        run_reply_count += 1
        run_replies.add(home_host_ip[0][1])
    print(FORMAT_TEMPLATE.format(
        "lookup",
        HOST_INTERNET_INTERFACE_ID,
        ",host_location={},host_name={},host_resolver={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            HOST_INTERNET_INTERFACE_ID,
            " ip=\"{}\",".format(
                home_host_ip[0][1]
            ) if home_host_ip is not None and len(home_host_ip) > 0 and len(home_host_ip[0]) > 1 and home_host_ip[0][1] != "" else " "),
        run_code_iteration,
        time_ms() - time_start_iteration,
        time_ns()))
    home_host_ip = None
    run_code_iteration = RUN_CODE_FAIL_NETWORK
    time_start_iteration = time_ms()
    try:
        home_host_ip = gethostbyname(HOST_HOME_NAME)
    except Exception as exception:
        print("Error processing DNS lookup [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
    if home_host_ip is not None and home_host_ip != "":
        run_code_iteration = RUN_CODE_SUCCESS
        run_reply_count += 1
        run_replies.add(home_host_ip)
    print(FORMAT_TEMPLATE.format(
        "lookup",
        HOST_INTERNET_INTERFACE_ID,
        ",host_location={},host_name={},host_resolver={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            "127.0.0.1",
            " ip=\"{}\",".format(
                home_host_ip
            ) if home_host_ip is not None else " "),
        run_code_iteration,
        time_ms() - time_start_iteration,
        time_ns()))
    for home_host_resolver_ip in RESOLVER_IPS:
        home_host_reply = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start_iteration = time_ms()
        try:
            home_host_resolver = Resolver()
            home_host_resolver.nameservers = [home_host_resolver_ip]
            home_host_replies = home_host_resolver.query(HOST_HOME_NAME, lifetime=SERVICE_TIMEOUT_SECONDS)
            if home_host_replies is not None and len(home_host_replies) == 1:
                home_host_reply = home_host_replies[0]
        except Exception as exception:
            print("Error processing DNS lookup [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
        if home_host_reply is not None and home_host_reply.address is not None and home_host_reply.address != "":
            run_code_iteration = RUN_CODE_SUCCESS
            run_reply_count += 1
            run_replies.add(home_host_reply.address)
        print(FORMAT_TEMPLATE.format(
            "lookup",
            HOST_INTERNET_INTERFACE_ID,
            ",host_location={},host_name={},host_resolver={}{}".format(
                HOST_INTERNET_LOCATION,
                HOST_HOME_NAME,
                home_host_resolver_ip,
                " ip=\"{}\",".format(
                    home_host_reply.address
                ) if (home_host_reply is not None and home_host_reply.address is not None and home_host_reply.address != "") else " "),
            run_code_iteration,
            time_ms() - time_start_iteration,
            time_ns()))
    run_code = RUN_CODE_SUCCESS if (run_reply_count == len(RESOLVER_IPS) + 2 and len(run_replies) == 1) else RUN_CODE_FAIL_NETWORK
    uptime_new = 0
    uptime_now = datetime.now(pytz.utc)
    uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
    try:
        uptime_rows = query(profile, QUERY_UPTIME.format("lookup"))
        if len(uptime_rows) == 0 or len(uptime_rows[0]) < 2 or run_code > RUN_CODE_SUCCESS:
            uptime_new = 0
        else:
            uptime_new = int((uptime_now - uptime_rows[0][0]).total_seconds())
    except Exception as exception:
        print("Error processing DNS lookup uptime [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
        run_code = RUN_CODE_FAIL_CONFIG
    print(FORMAT_TEMPLATE.format(
        "lookup",
        HOST_INTERNET_INTERFACE_ID,
        ",host_location={},host_name={},host_resolver={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            "*.*.*.*",
            " ip=\"{}\",uptime_s={},".format(
                run_replies.pop() if run_code == RUN_CODE_SUCCESS else "DNS not in sync",
                uptime_new
            )
        ),
        run_code,
        time_ms() - time_start,
        uptime_epoch))
    return run_code


def certficate(env):
    time_start = time_ms()
    run_code = RUN_CODE_FAIL_CONFIG
    uptime_new = 0
    uptime_now = datetime.now(pytz.utc)
    uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
    home_host_certificate_expiry = None
    try:
        home_host_connection = ssl.create_default_context().wrap_socket(socket.socket(socket.AF_INET), server_hostname=HOST_HOME_NAME)
        home_host_connection.settimeout(SERVICE_TIMEOUT_SECONDS)
        home_host_connection.connect((HOST_HOME_NAME, 443))
        home_host_certificate_expiry = \
            int((datetime.strptime(home_host_connection.getpeercert()['notAfter'], DATE_TLS) - datetime.now()).total_seconds())
    except Exception as exception:
        print("Error processing TLS certificate [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
        run_code = RUN_CODE_FAIL_NETWORK
    if home_host_certificate_expiry is not None and home_host_certificate_expiry > 600:
        run_code = RUN_CODE_SUCCESS
    try:
        uptime_rows = query(profile, QUERY_UPTIME.format("certifcate"))
        if len(uptime_rows) == 0 or len(uptime_rows[0]) < 2 or run_code > RUN_CODE_SUCCESS:
            uptime_new = 0
        else:
            uptime_new = int((uptime_now - uptime_rows[0][0]).total_seconds())
    except Exception as exception:
        print("Error processing TLS certificate [{}{}]"
              .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
        run_code = RUN_CODE_FAIL_CONFIG
    print(FORMAT_TEMPLATE.format(
        "certificate",
        HOST_INTERNET_INTERFACE_ID,
        ",host_location={},host_name={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            " expiry_s={},uptime_s={},".format(
                home_host_certificate_expiry if home_host_certificate_expiry is not None else 0,
                uptime_new
            )
        ),
        run_code,
        time_ms() - time_start,
        uptime_epoch))
    return run_code


if __name__ == "__main__":
    time_start_all = time_ms()
    profile_path = DEFAULT_PROFILE_PATH if len(sys.argv) == 1 else sys.argv[1]
    profile = None
    try:
        with open(profile_path, 'r') as profile_file:
            profile = load_profile(profile_file)
    except Exception as exception:
        print("Error processing profile [{}] [{}{}]"
              .format(profile_path, type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
    if profile is not None:
        run_code_all = []
        up_code = 0

        # run_code_all.append(ping(profile))
        # up_code += run_code_all[-1]

        # TODO: Temporarily disable upload/download speed tests
        # run_code_all.append(upload(profile))
        # up_code += run_code_all[-1]
        # run_code_all.append(download(profile))
        # up_code += run_code_all[-1]

        # run_code_all.append(lookup(profile))
        # up_code += run_code_all[-1]

        run_code_all.append(certficate(profile))
        up_code += run_code_all[-1]

        run_code_uptime = RUN_CODE_FAIL_CONFIG
        uptime_new = None
        uptime_now = datetime.now(pytz.utc)
        uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
        try:
            uptime_rows = query(profile, QUERY_UPTIME.format("uptime"))
            if len(uptime_rows) == 0 or len(uptime_rows[0]) < 2 or up_code > RUN_CODE_SUCCESS:
                uptime_new = 0
            else:
                uptime_new = int((uptime_now - uptime_rows[0][0]).total_seconds()) + int(uptime_rows[0][1])
        except Exception as exception:
            print("Error processing uptime [{}{}]"
                  .format(type(exception).__name__, "" if str(exception) == "" else ":{}".format(exception)), file=sys.stderr)
        if uptime_new is not None and uptime_epoch is not None:
            run_code_uptime = RUN_CODE_SUCCESS
        print(FORMAT_TEMPLATE.format(
            "uptime",
            HOST_INTERNET_INTERFACE_ID,
            ",host_location={},host_name={}{}metrics_suceeded={},metrics_failed={},".format(
                HOST_INTERNET_LOCATION,
                HOST_HOME_NAME,
                " uptime_s={},".format(
                    uptime_new
                ) if uptime_new is not None else " ",
                run_code_all.count(0) + (1 if run_code_uptime == RUN_CODE_SUCCESS else 0),
                len(run_code_all) - run_code_all.count(0) + (1 if run_code_uptime != RUN_CODE_SUCCESS else 0)),
            run_code_uptime,
            time_ms() - time_start_all,
            uptime_epoch))
