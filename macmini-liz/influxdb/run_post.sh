#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
. config/.profile

if [ ! -f "${SERVICE_HOME}/configs" ]; then
  apt-get install -y jq=1.5+dfsg-2+b1 curl=7.64.0-4+deb10u1 expect=5.45.4-2
  influx setup -o home -b asystem -u influxdb -p ${INFLUXDB_KEY} -t ${INFLUXDB_TOKEN} -f
  influx bucket create -n hosts -r 7d
  for BUCKET in asystem hosts; do
    export BUCKET_ID=$(influx bucket list -o home -n ${BUCKET} --json | jq -r '.[0].id')
    influx v1 dbrp create -o home --db ${BUCKET} --rp default --default --bucket-id ${BUCKET_ID}
    influx v1 auth create -o home --username influxdb_${BUCKET} --read-bucket ${BUCKET_ID}
    cat <<EOF >>auth_create.exp
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
spawn influx v1 auth create -o home --username influxdb_$env(BUCKET) --read-bucket $env(BUCKET_ID)
match_max 100000
expect -exact "[36mPlease type your password[0m: "
send -- "$env(INFLUXDB_KEY)\r"
expect -exact "
\r
[36mPlease type your password again[0m: "
send -- "$env(INFLUXDB_KEY)\r"
expect eof
EOF
    expect auth_create.exp
    curl -G --silent --request GET "http://influxdb_${BUCKET}:${INFLUXDB_KEY}@localhost:8086/query?db=${BUCKET}" \
      --data-urlencode "q=SELECT count(*) FROM test_metric WHERE time >= now() - 15m"
  done
fi
