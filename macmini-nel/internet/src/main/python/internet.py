# Ping: https://github.com/certator/pyping
# Throughput: https://github.com/sivel/speedtest-cli/wiki
# DNS: https://docs.python.org/2/library/socket.html#socket.gethostbyname
# InfluxDB: https://docs.influxdata.com/influxdb/v2.0/tools/client-libraries/python/
# Telegraf: https://github.com/influxdata/telegraf/tree/master/plugins/serializers/influx

# internet,operation=ping,host=janeandgraham.com average_response_msec=23.066,ttl=63,maximum_response_msec=24.64,
# minimum_response_msec=22.451,packets_received=5i,packets_transmitted=5i,percent_packet_loss=0,result_code=0i 1535747258000000000
# internet,operation=ping,host=per1.speedtest.telstra.net average_response_msec=23.066,ttl=63,maximum_response_msec=24.64,
# minimum_response_msec=22.451,packets_received=5i,packets_transmitted=5i,percent_packet_loss=0,result_code=0i 1535747258000000000

# Introduce random element to drop frequency, repeat InfluxDB last() if not executed
# internet,operation=upload,host=per1.speedtest.telstra.net ping_msec=23,transfer_bytes=100,rate_bytes_sec=100,result_code=0i
# 1535747258000000000
# internet,operation=download,host=per1.speedtest.telstra.net ping_msec=23,transfer_bytes=100,rate_bytes_sec=100,result_code=0i
# 1535747258000000000

# internet,operation=lookup,host=google.com response_msec=23,ip=10.0.0.1,result_code=0i 1535747258000000000
# internet,operation=lookup,host=janeandgraham.com response_msec=23,ip=10.0.0.1,result_code=0i 1535747258000000000

# Determined by if ping/download/upload are all successful, use InfluxDB last() to incrament uptime by timestamp diff, otherwise down and 0
# internet,operation=uptime uptime_sec=90000,status=up 1535747258000000000

# TODO:
# - Test for all exceptions, wrong codes, pull ethernet, pull modem etc
# - Add InfluxDB logic (throughput run, throughput echo/new, uptime calcualtion)
# - Add configurable .profile location and pass into docker container
# - Add unit tests against run codes, happy paths
# - Develop grafana graphs
# - Add a delay and repeat if we get a fail
# - Add a DNS flush (or connect direct to root DNS server) for lookup

from __future__ import print_function

import time
from socket import gethostbyname

from requests import post
from speedtest import Speedtest

HOST_HOME_NAME = "home.janeandgraham.com"
HOST_SPEEDTEST_PING_IDS = ["6359", "4153"]
HOST_SPEEDTEST_THROUGHPUT_IDS = ["2627", "30932", "7581"]

PING_COUNT = 1

RUN_CODE_SUCCESS = 0
RUN_CODE_FAIL_CONFIG = 1
RUN_CODE_FAIL_NETWORK = 2

FORMAT_PING = "internet,metric=ping,location={},host={} ping_min_ms={},ping_max_ms={},ping_med_ms={},pings_lost={},run_code={},run_ms={} {}"
FORMAT_UPLOAD = "internet,metric=upload,location={},host={} upload_mbps={},upload_bytes={},run_code={},run_ms={} {}"
FORMAT_DOWNLOAD = "internet,metric=download,location={},host={} download_mbps={},download_bytes={},run_code={},run_ms={} {}"
FORMAT_LOOKUP = "internet,metric=lookup,location={},host={} ip={},run_code={},run_ms={} {}"
FORMAT_UPTIME = "internet,metric=uptime,location={},host={} uptime_s={},run_code={},run_ms={} {}"


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
    return profile


def time_ms():
    return int(time.time() * 1000)


def time_ns():
    return int(time.time() * 1000000000)


def med(data):
    data.sort()
    mid = len(data) // 2
    return (data[mid] + data[~mid]) / 2


def state():
    with open("../resources/config/.profile", 'r') as profile_file:
        p = load_profile(profile_file)

        r = post(
            url="http://192.168.1.10:8086/api/v2/query?org=home",
            headers={
                'Authorization': 'Token {}'.format(p["INFLUXDB_TOKEN"]),
                'Accept': 'application/csv',
                'Content-type': 'application/vnd.flux'
            },
            data="""
from(bucket: "hosts")
    |> range(start: -1m, stop: now())
    |> filter(fn: (r) => r["_measurement"] == "cpu")
    |> keep(columns: ["_value", "_time"])
    |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
    |> group()
    |> last()
            """)
        print("cpu={}".format(r.content.split("\n")[1].split(",")[5]))


def ping():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS + HOST_SPEEDTEST_PING_IDS:
        time_start = time_ms()
        pings = []
        for i in xrange(PING_COUNT):
            try:
                speedtest = Speedtest()
                speedtest.get_servers([host_speedtest_id])
                speedtest.get_best_server()
                speedtest_results = speedtest.results.dict()
                pings.append(speedtest_results["ping"])
            except:
                None
        run_code_host = RUN_CODE_SUCCESS if len(pings) > 0 else RUN_CODE_FAIL_NETWORK
        if run_code > 0 and run_code_host == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        print(FORMAT_PING.format(
            speedtest.best["name"].lower(),
            speedtest.best["host"].split(":")[0],
            min(pings) if len(pings) > 0 else "",
            max(pings) if len(pings) > 0 else "",
            med(pings) if len(pings) > 0 else "",
            PING_COUNT - len(pings),
            run_code_host,
            time_ms() - time_start,
            time_ns()))
    return run_code


def upload():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS:
        time_start = time_ms()
        speedtest = Speedtest()
        speedtest.get_servers([host_speedtest_id])
        speedtest.upload()
        speedtest_results = speedtest.results.dict()
        run_code_host = RUN_CODE_SUCCESS if speedtest_results["upload"] > 0 else RUN_CODE_FAIL_NETWORK
        if run_code > 0 and run_code_host == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        print(FORMAT_UPLOAD.format(
            speedtest.best["name"].lower(),
            speedtest.best["host"].split(":")[0],
            speedtest_results["upload"] / 8000000,
            speedtest_results["bytes_sent"],
            run_code_host,
            time_ms() - time_start,
            time_ns()))
    return run_code


def download():
    run_code = RUN_CODE_FAIL_CONFIG
    for host_speedtest_id in HOST_SPEEDTEST_THROUGHPUT_IDS:
        time_start = time_ms()
        speedtest = Speedtest()
        speedtest.get_servers([host_speedtest_id])
        speedtest.download()
        speedtest_results = speedtest.results.dict()
        run_code_host = RUN_CODE_SUCCESS if speedtest_results["download"] > 0 else RUN_CODE_FAIL_NETWORK
        if run_code > 0 and run_code_host == RUN_CODE_SUCCESS:
            run_code = RUN_CODE_SUCCESS
        print(FORMAT_DOWNLOAD.format(
            speedtest.best["name"].lower(),
            speedtest.best["host"].split(":")[0],
            speedtest_results["download"] / 8000000,
            speedtest_results["bytes_received"],
            run_code_host,
            time_ms() - time_start,
            time_ns()))
    return run_code


def lookup():
    run_code = RUN_CODE_FAIL_CONFIG
    time_start = time_ms()
    home_host_ip = gethostbyname(HOST_HOME_NAME)
    if home_host_ip is not None and home_host_ip != "":
        run_code = RUN_CODE_SUCCESS
    print(FORMAT_LOOKUP.format(
        "darlington",
        HOST_HOME_NAME,
        home_host_ip,
        run_code,
        time_ms() - time_start,
        time_ns()))
    return run_code


if __name__ == "__main__":
    time_start = time_ms()
    run_code = RUN_CODE_SUCCESS
    run_code += ping()
    run_code += upload()
    run_code += download()
    run_code += lookup()
    print(FORMAT_UPTIME.format(
        "darlington",
        HOST_HOME_NAME,
        0,
        run_code,
        time_ms() - time_start,
        time_ns()))
