#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Influx custom setup initialising ..."
echo "--------------------------------------------------------------------------------"

apt-get install -y jq=1.5+dfsg-2+b1 curl=7.64.0-4+deb10u2 expect=5.45.4-2 netcat=1.10-41.1
while ! nc -z $INFLUXDB_HOST $INFLUXDB_PORT; do
  sleep 1
done

while ! influx ping --host http://${INFLUXDB_IP}:${INFLUXDB_PORT}; do
  sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Influx custom setup starting ..."
echo "--------------------------------------------------------------------------------"

if [ ! -f "/root/.influxdbv2/configs" ] || [ $(grep remote /root/.influxdbv2/configs | wc -l) -ne 1 ]; then
  influx config create -a -n remote -u http://${INFLUXDB_IP}:${INFLUXDB_PORT} -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN}
fi
if [ ! -f "/root/.influxdbv2/configs" ] || [ $(grep default /root/.influxdbv2/configs | wc -l) -ne 1 ]; then
  influx setup -f -n default --host http://${INFLUXDB_IP}:${INFLUXDB_PORT} -o ${INFLUXDB_ORG} -b ${INFLUXDB_BUCKET_HOME_PUBLIC} -u ${INFLUXDB_USER} -p ${INFLUXDB_KEY} -t ${INFLUXDB_TOKEN}
fi

BUCKET_ID_HOME_PUBLIC=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PUBLIC} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
if [ "${BUCKET_ID_HOME_PUBLIC}" = "" ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PUBLIC} -r 0 -t ${INFLUXDB_TOKEN}
  BUCKET_ID_HOME_PUBLIC=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PUBLIC} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
fi
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PUBLIC} | grep ${BUCKET_ID_HOME_PUBLIC} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOME_PUBLIC} --rp default --default --bucket-id ${BUCKET_ID_HOME_PUBLIC} -t ${INFLUXDB_TOKEN}
fi

BUCKET_ID_HOME_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
if [ "${BUCKET_ID_HOME_PRIVATE}" = "" ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PRIVATE} -r 0 -t ${INFLUXDB_TOKEN}
  BUCKET_ID_HOME_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
fi
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PRIVATE} | grep ${BUCKET_ID_HOME_PRIVATE} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOME_PRIVATE} --rp default --default --bucket-id ${BUCKET_ID_HOME_PRIVATE} -t ${INFLUXDB_TOKEN}
fi

BUCKET_ID_HOST_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOST_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
if [ "${BUCKET_ID_HOST_PRIVATE}" = "" ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOST_PRIVATE} -r 0 -t ${INFLUXDB_TOKEN}
  BUCKET_ID_HOST_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOST_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
fi
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOST_PRIVATE} | grep ${BUCKET_ID_HOST_PRIVATE} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOST_PRIVATE} --rp default --default --bucket-id ${BUCKET_ID_HOST_PRIVATE} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep "Read public buckets" | wc -l) -eq 0 ]; then
  influx auth create -o ${INFLUXDB_ORG} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    -d "Read public buckets" -t ${INFLUXDB_TOKEN}
fi
if [ $(influx v1 auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_USER_PUBLIC} | wc -l) -ne 1 ]; then
  influx v1 auth create -o ${INFLUXDB_ORG} --username ${INFLUXDB_USER_PUBLIC} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --password ${INFLUXDB_TOKEN_PUBLIC_V1} -d "Read public buckets" -t ${INFLUXDB_TOKEN}
fi
if [ $(influx v1 auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_USER_ALL} | wc -l) -ne 1 ]; then
  influx v1 auth create -o ${INFLUXDB_ORG} --username ${INFLUXDB_USER_ALL} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --read-bucket ${BUCKET_ID_HOME_PRIVATE} \
    --read-bucket ${BUCKET_ID_HOST_PRIVATE} \
    --write-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --write-bucket ${BUCKET_ID_HOME_PRIVATE} \
    --write-bucket ${BUCKET_ID_HOST_PRIVATE} \
    --password ${INFLUXDB_TOKEN} -d "Read/Write all buckets" -t ${INFLUXDB_TOKEN}
fi

echo "--------------------------------------------------------------------------------"
echo "Influx custom setup finished"
echo "--------------------------------------------------------------------------------"
