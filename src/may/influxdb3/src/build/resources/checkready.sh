true
#[ $(curl "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}/api/v3/configure/database?format=csv&show_deleted=false" | grep -c host_private) -eq 1 ]
