# Ping: https://github.com/alessandromaggio/pythonping https://github.com/romana/multi-ping
# Throughput: https://github.com/sivel/speedtest-cli/wiki
# DNS: https://docs.python.org/2/library/socket.html#socket.gethostbyname
# InfluxDB: https://docs.influxdata.com/influxdb/v2.0/tools/client-libraries/python/
# Telegraf: https://github.com/influxdata/telegraf/tree/master/plugins/serializers/influx

# HOST_ID=("2627" "5029" "27260")
# HOST_NAME=("per1.speedtest.telstra.net" "nyc.speedtest.sbcglobal.net" "speedtest.ukbroadband.com")

# internet,operation=ping,host=janeandgraham.com average_response_msec=23.066,ttl=63,maximum_response_msec=24.64,minimum_response_msec=22.451,packets_received=5i,packets_transmitted=5i,percent_packet_loss=0,result_code=0i 1535747258000000000
# internet,operation=ping,host=per1.speedtest.telstra.net average_response_msec=23.066,ttl=63,maximum_response_msec=24.64,minimum_response_msec=22.451,packets_received=5i,packets_transmitted=5i,percent_packet_loss=0,result_code=0i 1535747258000000000

# Introduce random element to drop frequency, repeat InfluxDB last() if not executed
# internet,operation=upload,host=per1.speedtest.telstra.net ping_msec=23,transfer_bytes=100,rate_bytes_sec=100,result_code=0i 1535747258000000000
# internet,operation=download,host=per1.speedtest.telstra.net ping_msec=23,transfer_bytes=100,rate_bytes_sec=100,result_code=0i 1535747258000000000

# internet,operation=lookup,host=google.com response_msec=23,ip=10.0.0.1,result_code=0i 1535747258000000000
# internet,operation=lookup,host=janeandgraham.com response_msec=23,ip=10.0.0.1,result_code=0i 1535747258000000000

# Determined by if ping/download/upload are all successful, use InfluxDB last() to incrament uptime by timestamp diff, otherwise down and 0
# internet,operation=uptime uptime_sec=90000,status=up 1535747258000000000
