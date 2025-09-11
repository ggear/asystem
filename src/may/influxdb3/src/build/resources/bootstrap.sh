influxdb3 create token --admin --host ${INFLUXDB3_API_URL} | grep -v "token name already exists, _admin" || true

# TODO: Work out if a REST API exists to create databases, else raise feature request for REST API doc or HTTP_BIND_ADDRESS respect, or both
