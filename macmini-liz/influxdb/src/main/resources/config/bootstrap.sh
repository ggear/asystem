#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Influx bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! influx ping --host http://${INFLUXDB_HOST}:${INFLUXDB_PORT} >>/dev/null 2>&1; do
  echo "Waiting for influxdb to come up ..." && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Influx bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

if [ ! -f "/root/.influxdbv2/configs" ] || [ $(grep remote /root/.influxdbv2/configs | wc -l) -ne 1 ]; then
  influx config create -a -n remote -u http://${INFLUXDB_HOST}:${INFLUXDB_PORT} -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN}
fi
if [ ! -f "/root/.influxdbv2/configs" ] || [ $(grep default /root/.influxdbv2/configs | wc -l) -ne 1 ]; then
  influx setup -f -n default --host http://${INFLUXDB_HOST}:${INFLUXDB_PORT} -o ${INFLUXDB_ORG} -b ${INFLUXDB_BUCKET_HOME_PUBLIC} -u ${INFLUXDB_USER} -p ${INFLUXDB_KEY} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx bucket list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PUBLIC} | wc -l) -eq 0 ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PUBLIC} -r 0 -t ${INFLUXDB_TOKEN}
fi
BUCKET_ID_HOME_PUBLIC=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PUBLIC} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
influx bucket update --id ${BUCKET_ID_HOME_PUBLIC} --shard-group-duration 7d -t ${INFLUXDB_TOKEN}
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PUBLIC} | grep ${BUCKET_ID_HOME_PUBLIC} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOME_PUBLIC} --rp default --default --bucket-id ${BUCKET_ID_HOME_PUBLIC} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx bucket list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PRIVATE} | wc -l) -eq 0 ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PRIVATE} -r 0 -t ${INFLUXDB_TOKEN}
fi
BUCKET_ID_HOME_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOME_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id')
influx bucket update --id ${BUCKET_ID_HOME_PRIVATE} --shard-group-duration 7d -t ${INFLUXDB_TOKEN}
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOME_PRIVATE} | grep ${BUCKET_ID_HOME_PRIVATE} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOME_PRIVATE} --rp default --default --bucket-id ${BUCKET_ID_HOME_PRIVATE} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx bucket list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_DATA_PUBLIC} | wc -l) -eq 0 ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_DATA_PUBLIC} -r 0 -t ${INFLUXDB_TOKEN}
fi
BUCKET_ID_DATA_PUBLIC=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_DATA_PUBLIC} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id' 2>/dev/null)
influx bucket update --id ${BUCKET_ID_DATA_PUBLIC} --shard-group-duration 365d -t ${INFLUXDB_TOKEN}
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_DATA_PUBLIC} | grep ${BUCKET_ID_DATA_PUBLIC} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_DATA_PUBLIC} --rp default --default --bucket-id ${BUCKET_ID_DATA_PUBLIC} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx bucket list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_DATA_PRIVATE} | wc -l) -eq 0 ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_DATA_PRIVATE} -r 0 -t ${INFLUXDB_TOKEN}
fi
BUCKET_ID_DATA_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_DATA_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id')
influx bucket update --id ${BUCKET_ID_DATA_PRIVATE} --shard-group-duration 365d -t ${INFLUXDB_TOKEN}
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_DATA_PRIVATE} | grep ${BUCKET_ID_DATA_PRIVATE} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_DATA_PRIVATE} --rp default --default --bucket-id ${BUCKET_ID_DATA_PRIVATE} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx bucket list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOST_PRIVATE} | wc -l) -eq 0 ]; then
  influx bucket create -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOST_PRIVATE} -r 0 -t ${INFLUXDB_TOKEN}
fi
BUCKET_ID_HOST_PRIVATE=$(influx bucket list -o ${INFLUXDB_ORG} -n ${INFLUXDB_BUCKET_HOST_PRIVATE} -t ${INFLUXDB_TOKEN} --json | jq -r '.[0].id')
influx bucket update --id ${BUCKET_ID_HOST_PRIVATE} --shard-group-duration 1d -t ${INFLUXDB_TOKEN}
if [ $(influx v1 dbrp list -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_BUCKET_HOST_PRIVATE} | grep ${BUCKET_ID_HOST_PRIVATE} | wc -l) -ne 1 ]; then
  influx v1 dbrp create -o ${INFLUXDB_ORG} --db ${INFLUXDB_BUCKET_HOST_PRIVATE} --rp default --default --bucket-id ${BUCKET_ID_HOST_PRIVATE} -t ${INFLUXDB_TOKEN}
fi

if [ $(influx auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep "Read public buckets" | wc -l) -eq 0 ]; then
  influx auth create -o ${INFLUXDB_ORG} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --read-bucket ${BUCKET_ID_DATA_PUBLIC} \
    -d "Read public buckets" -t ${INFLUXDB_TOKEN}
fi
if [ $(influx v1 auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_USER_PUBLIC} | wc -l) -ne 1 ]; then
  influx v1 auth create -o ${INFLUXDB_ORG} --username ${INFLUXDB_USER_PUBLIC} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --read-bucket ${BUCKET_ID_DATA_PUBLIC} \
    --password ${INFLUXDB_TOKEN_PUBLIC_V1} -d "Read public buckets" -t ${INFLUXDB_TOKEN}
fi
if [ $(influx v1 auth list -o ${INFLUXDB_ORG} -t ${INFLUXDB_TOKEN} | grep ${INFLUXDB_USER_ALL} | wc -l) -ne 1 ]; then
  influx v1 auth create -o ${INFLUXDB_ORG} --username ${INFLUXDB_USER_ALL} \
    --read-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --read-bucket ${BUCKET_ID_HOME_PRIVATE} \
    --read-bucket ${BUCKET_ID_DATA_PUBLIC} \
    --read-bucket ${BUCKET_ID_DATA_PRIVATE} \
    --read-bucket ${BUCKET_ID_HOST_PRIVATE} \
    --write-bucket ${BUCKET_ID_HOME_PUBLIC} \
    --write-bucket ${BUCKET_ID_HOME_PRIVATE} \
    --write-bucket ${BUCKET_ID_DATA_PUBLIC} \
    --write-bucket ${BUCKET_ID_DATA_PRIVATE} \
    --write-bucket ${BUCKET_ID_HOST_PRIVATE} \
    --password ${INFLUXDB_TOKEN} -d "Read/Write all buckets" -t ${INFLUXDB_TOKEN}
fi

echo "--------------------------------------------------------------------------------"
echo "Influx bootstrap finished"
echo "--------------------------------------------------------------------------------"
