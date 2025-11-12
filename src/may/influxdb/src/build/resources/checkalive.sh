[ -d "$(influx server-config | jq -r '.["engine-path"]')" ] &&
  [ -w "$(influx server-config | jq -r '.["engine-path"]')" ]
