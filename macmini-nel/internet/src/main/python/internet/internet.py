import datetime
import os
import socket
import ssl
import sys
import time
import traceback
from datetime import datetime
from socket import gethostbyname

import pytz
from dateutil.parser import parse
from dns.resolver import Resolver
from requests import post
from speedtest import NoMatchedServers
from speedtest import Speedtest

HOST_HOME_NAME = "home.janeandgraham.com"

HOST_SPEEDTEST_PING_IDS = []
HOST_SPEEDTEST_THROUGHPUT_ID = "12494"

RESOLVER_IPS = ["10.0.0.1", "162.159.44.190", "1.1.1.1", "8.8.8.8"]

HOST_INTERNET_LOCATION = "darlington"
HOST_INTERNET_INTERFACE_ID = "udm-rack-eth8"

PING_COUNT = 3
PING_SLEEP_SECONDS = 1
THROUGHPUT_PERIOD_SECONDS = 6 * 60 * 60
SERVICE_TIMEOUT_SECONDS = 2
STACKTRACE_REFERENCE_LIMIT = 1

RUN_CODE_REPEAT = -1
RUN_CODE_SUCCESS = 0
RUN_CODE_FAIL_CONFIG = 1
RUN_CODE_FAIL_NETWORK = 2
RUN_CODE_FAIL_SPEEDTEST = 3
RUN_CODE_FAIL_ZEROED = 4

DATE_TLS = r'%b %d %H:%M:%S %Y %Z'

FORMAT_TEMPLATE = "internet,metric={},host_id={},run_code={}{}run_ms={} {}"

QUERY_UPTIME = """
from(bucket: "host_private")
  |> range(start: -10m, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "{}")
  |> filter(fn: (r) => r["metric"] == "{}")
  |> keep(columns: ["_value", "_time"])
  |> sort(columns: ["_time"])
  |> last()
  |> group()
"""

QUERY_LAST = """
from(bucket: "host_private")
  |> range(start: -24h, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => {})
  |> filter(fn: (r) => r["metric"] == "{}" {})
  |> keep(columns: ["_time", "_value", "metric", "host_id", "host_name", "host_location"])
  |> sort(columns: ["_time"])
  |> last()
  |> group()
"""


def time_ms():
    return int(time.time() * 1000)


def time_ns():
    return int(time.time() * 1000000000)


def med(data):
    data.sort()
    mid = len(data) // 2
    return (data[mid] + data[~mid]) / 2


def query(flux):
    response = post(
        url="http://{}:{}/api/v2/query?org={}".format(os.environ["INFLUXDB_IP"], os.environ["INFLUXDB_PORT"], os.environ["INFLUXDB_ORG"]),
        headers={
            'Accept': 'application/csv',
            'Content-type': 'application/vnd.flux',
            'Authorization': 'Token {}'.format(os.environ["INFLUXDB_TOKEN"])
        }, data=flux)
    rows = []
    for row in response.text.strip().split("\n")[1:]:
        cols = row.strip().split(",")
        if len(cols) > 4:
            rows.append([parse(cols[3])] + cols[4:])
    return rows


def ping():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in [HOST_SPEEDTEST_THROUGHPUT_ID] + HOST_SPEEDTEST_PING_IDS:
        pings = []
        host_speedtest = None
        time_start = time_ms()
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        for i in range(PING_COUNT):
            try:
                speedtest = Speedtest()
                try:
                    speedtest.get_servers([host_speedtest_id])
                except Exception:
                    pass
                host_speedtest = speedtest.best
                speedtest_results = speedtest.results.dict()
                pings.append(speedtest_results["ping"])
                if i < PING_COUNT - 1:
                    time.sleep(PING_SLEEP_SECONDS)
                    time_start += PING_SLEEP_SECONDS * 1000
            except NoMatchedServers:
                run_code_iteration = RUN_CODE_FAIL_SPEEDTEST
            except Exception as exception:
                print("Error processing speedtest ping - ", end="", file=sys.stderr)
                traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
                run_code_iteration = RUN_CODE_FAIL_CONFIG
        run_code_iteration = RUN_CODE_SUCCESS \
            if (len(pings) > 0 and max(pings) > 0) else run_code_iteration
        if run_code > RUN_CODE_SUCCESS:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "ping",
            "speedtest-" + host_speedtest["id"],
            run_code_iteration,
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
            time_ms() - time_start,
            time_ns()))
    return run_code


def upload():
    run_code = RUN_CODE_SUCCESS
    throughput_run = True
    network_stats = {
        "upload": [
            """ r["_field"] == "upload_mbps" """,
            """ and r["run_code"] == "0" """,
            ",host_location={},host_name={} upload_mbps={},",
        ],
    }
    for network_stat in network_stats:
        time_start = time_ms()
        try:
            for network_stat_reply in \
                    query(QUERY_LAST.format(network_stats[network_stat][0], network_stat, network_stats[network_stat][1])):
                if ((datetime.now(pytz.utc) - network_stat_reply[0]).total_seconds()) < THROUGHPUT_PERIOD_SECONDS:
                    throughput_run = False
                    print(FORMAT_TEMPLATE.format(
                        network_stat,
                        network_stat_reply[2],
                        RUN_CODE_REPEAT,
                        network_stats[network_stat][2].format(network_stat_reply[3], network_stat_reply[4], network_stat_reply[1]),
                        time_ms() - time_start,
                        time_ns()))
        except Exception as exception:
            print("Error processing speedtest upload - ", end="", file=sys.stderr)
            traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
            run_code = RUN_CODE_FAIL_CONFIG
    if throughput_run:
        host_speedtest = None
        results_speedtest = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start = time_ms()
        try:
            speedtest = Speedtest()
            try:
                speedtest.get_servers([HOST_SPEEDTEST_THROUGHPUT_ID])
            except Exception:
                pass
            host_speedtest = speedtest.best
            speedtest.upload()
            results_speedtest = speedtest.results.dict()
        except NoMatchedServers:
            run_code_iteration = RUN_CODE_FAIL_SPEEDTEST
        except Exception as exception:
            print("Error processing speedtest upload - ", end="", file=sys.stderr)
            traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
            run_code_iteration = RUN_CODE_FAIL_NETWORK
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "upload" in results_speedtest and results_speedtest["upload"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "upload",
            "speedtest-" + host_speedtest["id"],
            run_code_iteration,
            "{} upload_mbps={},upload_b={},".format(
                ",host_location={},host_name={}".format(
                    host_speedtest["name"].lower(),
                    host_speedtest["host"].split(":")[0]
                ) if host_speedtest is not None else "",
                results_speedtest["upload"] / 8000000,
                results_speedtest["bytes_sent"]
            ) if results_speedtest is not None else " ",
            time_ms() - time_start,
            time_ns()))
    return run_code


def download():
    run_code = RUN_CODE_SUCCESS
    throughput_run = True
    network_stats = {
        "download": [
            """ r["_field"] == "download_mbps" """,
            """ and r["run_code"] == "0" """,
            ",host_location={},host_name={} download_mbps={},",
        ],
    }
    for network_stat in network_stats:
        time_start = time_ms()
        try:
            for network_stat_reply in \
                    query(QUERY_LAST.format(network_stats[network_stat][0], network_stat, network_stats[network_stat][1])):
                if ((datetime.now(pytz.utc) - network_stat_reply[0]).total_seconds()) < THROUGHPUT_PERIOD_SECONDS:
                    throughput_run = False
                    print(FORMAT_TEMPLATE.format(
                        network_stat,
                        network_stat_reply[2],
                        RUN_CODE_REPEAT,
                        network_stats[network_stat][2].format(network_stat_reply[3], network_stat_reply[4], network_stat_reply[1]),
                        time_ms() - time_start,
                        time_ns()))
        except Exception as exception:
            print("Error processing speedtest download - ", end="", file=sys.stderr)
            traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
            run_code = RUN_CODE_FAIL_CONFIG
    if throughput_run:
        host_speedtest = None
        results_speedtest = None
        run_code_iteration = RUN_CODE_FAIL_NETWORK
        time_start = time_ms()
        try:
            speedtest = Speedtest()
            try:
                speedtest.get_servers([HOST_SPEEDTEST_THROUGHPUT_ID])
            except Exception:
                pass
            host_speedtest = speedtest.best
            speedtest.download()
            results_speedtest = speedtest.results.dict()
        except NoMatchedServers:
            run_code_iteration = RUN_CODE_FAIL_SPEEDTEST
        except Exception as exception:
            print("Error processing speedtest download - ", end="", file=sys.stderr)
            traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
            run_code_iteration = RUN_CODE_FAIL_NETWORK
        run_code_iteration = RUN_CODE_SUCCESS \
            if (results_speedtest is not None and "download" in results_speedtest and results_speedtest["download"] > 0) \
            else run_code_iteration
        if run_code > RUN_CODE_SUCCESS and run_code_iteration == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        else:
            run_code = run_code_iteration
        print(FORMAT_TEMPLATE.format(
            "download",
            "speedtest-" + host_speedtest["id"],
            run_code_iteration,
            "{} download_mbps={},download_b={},".format(
                ",host_location={},host_name={}".format(
                    host_speedtest["name"].lower(),
                    host_speedtest["host"].split(":")[0]
                ) if host_speedtest is not None else "",
                results_speedtest["download"] / 8000000,
                results_speedtest["bytes_received"]
            ) if results_speedtest is not None else " ",
            time_ms() - time_start,
            time_ns()))
    return run_code


def lookup():
    time_start = time_ms()
    run_replies = set()
    run_reply_count = 0
    home_host_ip = None
    run_code_iteration = RUN_CODE_FAIL_NETWORK
    time_start_iteration = time_ms()
    try:
        home_host_ip = gethostbyname(HOST_HOME_NAME)
    except Exception as exception:
        print("Error processing DNS lookup - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
    if home_host_ip is not None and home_host_ip != "":
        run_code_iteration = RUN_CODE_SUCCESS
        run_reply_count += 1
        run_replies.add(home_host_ip)
    print(FORMAT_TEMPLATE.format(
        "lookup",
        HOST_INTERNET_INTERFACE_ID,
        run_code_iteration,
        ",host_location={},host_name={},host_resolver={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            "127.0.0.1",
            " ip=\"{}\",".format(
                home_host_ip
            ) if home_host_ip is not None else " "),
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
            print("Error processing DNS lookup - ", end="", file=sys.stderr)
            traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
        if home_host_reply is not None and home_host_reply.address is not None and home_host_reply.address != "":
            run_code_iteration = RUN_CODE_SUCCESS
            run_reply_count += 1
            run_replies.add(home_host_reply.address)
        print(FORMAT_TEMPLATE.format(
            "lookup",
            HOST_INTERNET_INTERFACE_ID,
            run_code_iteration,
            ",host_location={},host_name={},host_resolver={}{}".format(
                HOST_INTERNET_LOCATION,
                HOST_HOME_NAME,
                home_host_resolver_ip,
                " ip=\"{}\",".format(
                    home_host_reply.address
                ) if (home_host_reply is not None and home_host_reply.address is not None and home_host_reply.address != "") else " "),
            time_ms() - time_start_iteration,
            time_ns()))
    run_code = RUN_CODE_SUCCESS if (run_reply_count == len(RESOLVER_IPS) + 1 and len(run_replies) == 1) else RUN_CODE_FAIL_NETWORK
    uptime_delta = 0
    uptime_now = datetime.now(pytz.utc)
    uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
    try:
        uptime_rows = query(QUERY_UPTIME.format("uptime_delta_s", "lookup"))
        if len(uptime_rows) > 0 and len(uptime_rows[0]) > 1 and run_code == RUN_CODE_SUCCESS:
            uptime_delta = int(round((uptime_now - uptime_rows[0][0]).total_seconds()))
    except Exception as exception:
        print("Error processing DNS lookup uptime - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
        run_code = RUN_CODE_FAIL_CONFIG
    print(FORMAT_TEMPLATE.format(
        "lookup",
        HOST_INTERNET_INTERFACE_ID,
        run_code,
        ",host_location={},host_name={},host_resolver={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            "*.*.*.*",
            " ip=\"{}\",uptime_delta_s={},".format(
                run_replies.pop() if run_code == RUN_CODE_SUCCESS else "unknown",
                uptime_delta
            )
        ),
        time_ms() - time_start,
        uptime_epoch))
    return run_code


def certificate():
    time_start = time_ms()
    run_code = RUN_CODE_FAIL_CONFIG
    home_host_certificate_expiry = None
    try:
        home_host_connection = ssl.create_default_context().wrap_socket(socket.socket(socket.AF_INET), server_hostname=HOST_HOME_NAME)
        home_host_connection.settimeout(SERVICE_TIMEOUT_SECONDS)
        home_host_connection.connect((HOST_HOME_NAME, 443))
        home_host_certificate_expiry = \
            int((datetime.strptime(home_host_connection.getpeercert()['notAfter'], DATE_TLS) - datetime.now()).total_seconds())
    except Exception as exception:
        print("Error processing TLS certificate - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
        run_code = RUN_CODE_FAIL_NETWORK
    if home_host_certificate_expiry is not None and home_host_certificate_expiry > 600:
        run_code = RUN_CODE_SUCCESS
    uptime_new = 0
    uptime_delta = 0
    uptime_now = datetime.now(pytz.utc)
    uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
    try:
        uptime_rows = query(QUERY_UPTIME.format("uptime_delta_s", "certificate"))
        if len(uptime_rows) > 0 and len(uptime_rows[0]) > 1 and run_code == RUN_CODE_SUCCESS:
            uptime_delta = int(round((uptime_now - uptime_rows[0][0]).total_seconds()))
            uptime_rows = query(QUERY_UPTIME.format("uptime_s", "certificate"))
            if len(uptime_rows) > 0 and len(uptime_rows[0]) > 1 and run_code == RUN_CODE_SUCCESS:
                uptime_new = uptime_delta + int(uptime_rows[0][1])
    except Exception as exception:
        print("Error processing TLS certificate - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
        run_code = RUN_CODE_FAIL_CONFIG
    print(FORMAT_TEMPLATE.format(
        "certificate",
        HOST_INTERNET_INTERFACE_ID,
        run_code,
        ",host_location={},host_name={}{}".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            " expiry_s={},uptime_delta_s={},uptime_s={},".format(
                home_host_certificate_expiry if home_host_certificate_expiry is not None else 0,
                uptime_delta,
                uptime_new
            )
        ),
        time_ms() - time_start,
        uptime_epoch))
    return run_code


def execute():
    time_start_all = time_ms()
    run_code_all = []
    up_code_network = True
    run_code_all.append(ping())
    up_code_network = run_code_all[-1] == RUN_CODE_SUCCESS or run_code_all[-1] == RUN_CODE_FAIL_SPEEDTEST
    if up_code_network:
        run_code_all.append(upload())
        run_code_all.append(download())
    run_code_all.append(lookup())
    run_code_all.append(certificate())
    run_code_uptime = RUN_CODE_FAIL_CONFIG
    uptime_delta = 0
    uptime_new = None
    uptime_now = datetime.now(pytz.utc)
    uptime_epoch = int((uptime_now - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000000000)
    try:
        uptime_rows = query(QUERY_UPTIME.format("uptime_s", "network"))
        if len(uptime_rows) == 0 or len(uptime_rows[0]) < 2 or not up_code_network:
            uptime_new = 0
        else:
            uptime_delta = int(round((uptime_now - uptime_rows[0][0]).total_seconds()))
            uptime_new = uptime_delta + int(uptime_rows[0][1])
    except Exception as exception:
        print("Error processing network - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
    if uptime_new is not None and uptime_epoch is not None:
        run_code_uptime = RUN_CODE_SUCCESS
    if not up_code_network:
        network_stats = {
            "ping": [
                """ r["_field"] == "ping_min_ms" """,
                "",
                ",host_location={},host_name={} ping_min_ms=0,ping_max_ms=0,ping_med_ms=0,"
            ],
            "upload": [
                """ r["_field"] == "upload_mbps" """,
                "",
                ",host_location={},host_name={} upload_mbps=0,upload_b=0,"
            ],
            "download": [
                """ r["_field"] == "download_mbps" """,
                "",
                ",host_location={},host_name={} download_mbps=0,download_b=0,"
            ],
        }
        for network_stat in network_stats:
            time_start = time_ms()
            try:
                for network_stat_reply in \
                        query(QUERY_LAST.format(network_stats[network_stat][0], network_stat, network_stats[network_stat][1])):
                    print(FORMAT_TEMPLATE.format(
                        network_stat,
                        network_stat_reply[2],
                        RUN_CODE_FAIL_ZEROED,
                        network_stats[network_stat][2].format(network_stat_reply[3], network_stat_reply[4]),
                        time_ms() - time_start,
                        time_ns()))
            except Exception as exception:
                print("Error processing network - ", end="", file=sys.stderr)
                traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
    run_code_failures = len(run_code_all) - run_code_all.count(0) + (1 if run_code_uptime != RUN_CODE_SUCCESS else 0)
    print(FORMAT_TEMPLATE.format(
        "network",
        HOST_INTERNET_INTERFACE_ID,
        run_code_uptime,
        ",host_location={},host_name={}{}metrics_suceeded={},metrics_failed={},".format(
            HOST_INTERNET_LOCATION,
            HOST_HOME_NAME,
            " uptime_delta_s={}{}".format(
                uptime_delta,
                ",uptime_s={},".format(
                    uptime_new
                ) if uptime_new is not None else ","
            ),
            len(run_code_all) + 1 - run_code_failures,
            run_code_failures),
        time_ms() - time_start_all, uptime_epoch))
    return run_code_failures


if __name__ == "__main__":
    execute()
