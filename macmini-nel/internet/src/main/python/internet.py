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

from __future__ import print_function

from socket import gethostbyname

from requests import post
from speedtest import Speedtest

HOSTS = ["2627", "30932", "2233"]


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


if __name__ == "__main__":

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

        for id in HOSTS:
            threads = 2
            s = Speedtest()
            s.get_servers([id])
            s.get_best_server()
            s.download(threads=threads)
            s.upload(threads=threads)
            r = s.results.dict()
            print("location={} host={} ping={} up={} down={} sent={} receive={}".format(
                s.best["name"].lower(),
                s.best["host"].split(":")[0],
                r["ping"],
                r["upload"] / 8000000,
                r["download"] / 8000000,
                r["bytes_sent"],
                r["bytes_received"]))

        r = gethostbyname("home.janeandgraham.com")
        print("host=home.janeandgraham.com ip={}".format(r))
