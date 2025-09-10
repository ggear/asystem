# TODO: Work out if a REST API exists to create databases, else raise feature request for REST API doc or HTTP_BIND_ADDRESS respect, or both
[ $(curl -sf "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}/api/v3/configure/database?format=csv&show_deleted=false" | grep -c host_private) -eq 0 ] && echo "Need to create database from outside of host!"
