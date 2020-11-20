#!/bin/sh

. /root/.influxdbv2/.profile

if [ ! -f "/root/.influxdbv2/configs" ]; then
  echo "Setup InfluxDB for first time ..."
  sleep 5
  influx setup -o home -b asystem -u influxdb -p ${INFLUXDB_KEY} -t ${INFLUXDB_TOKEN} -f >/dev/null 2>&1
  apt-get install -y jq=1.5+dfsg-2+b1 curl=7.64.0-4+deb10u1 expect=5.45.4-2
  influx bucket create -o home -n hosts -r 90d -t ${INFLUXDB_TOKEN}
  for BUCKET in asystem hosts; do
    export BUCKET=${BUCKET}
    export BUCKET_ID=$(influx bucket list -o home -n ${BUCKET} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id')
    influx v1 dbrp create -o home --db ${BUCKET} --rp default --default --bucket-id ${BUCKET_ID} -t ${INFLUXDB_TOKEN}
    cat <<EOF >>/root/.influxdbv2/setup_create_auth.exp
#!/usr/bin/expect -f
set force_conservative 0
if {$force_conservative} {
	set send_slow {1 .1}
	proc send {ignore arg} {
		sleep .1
		exp_send -s -- $arg
	}
}
set timeout -1
spawn influx v1 auth create -o home --username "influxdb_$env(BUCKET)" --read-bucket "$env(BUCKET_ID)" --write-bucket "$env(BUCKET_ID)" -t "$env(INFLUXDB_TOKEN)"
match_max 100000
expect -re {.*password.*}
send -- "$env(INFLUXDB_KEY)\r"
expect -re {.*password.*}
send -- "$env(INFLUXDB_KEY)\r"
expect eof
EOF
    expect /root/.influxdbv2/setup_create_auth.exp
    curl -G --silent --request GET "http://influxdb_${BUCKET}:${INFLUXDB_KEY}@localhost:8086/query?db=${BUCKET}" \
      --data-urlencode "q=SELECT count(*) FROM test_metric WHERE time >= now() - 15m"
  done
else
  echo "InfluxDB already setup  ..."
fi
