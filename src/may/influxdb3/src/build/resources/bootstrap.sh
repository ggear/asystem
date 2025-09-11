#if ! influxdb3 show tokens --format json 2>/dev/null | jq -e '.[] | select(.name=="_admin")' >/dev/null; then
#  influxdb3 create token --admin
#fi
influxdb3 show tokens
