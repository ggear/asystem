#!/bin/sh

CONF_FLUSHED_LEASES="false"
CONF_SOURCE_DIR="/mnt/data/udm-dnsmasq/dhcp.dhcpServers"
CONF_CURRENT_FILE="/mnt/data/udapi-config/dnsmasq.lease"
CONF_BUILD_DIR="/tmp/dnsmasq.conf.d_tmp"
CONF_BUILD_FILE="${CONF_BUILD_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_DIR="/run/dnsmasq.conf.d"
CONF_CUSTOM_FILE="${CONF_CUSTOM_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_FILES="dhcp.dhcpServers"*"custom.conf"

rm -rf ${CONF_BUILD_DIR}
cp -rvf ${CONF_CUSTOM_DIR} ${CONF_BUILD_DIR}
rm -rf ${CONF_BUILD_DIR}/${CONF_CUSTOM_FILES}
for CONF_SOURCE_FILE in $(ls ${CONF_SOURCE_DIR}-*Untagged*-custom.conf ${CONF_SOURCE_DIR}-*Management*-custom.conf ${CONF_SOURCE_DIR}-*Unfettered*-custom.conf ${CONF_SOURCE_DIR}-*Controlled*-custom.conf ${CONF_SOURCE_DIR}-*Isolated*-custom.conf 2>/dev/null); do
  while read CONF_SOURCE_LINE; do
    CONF_CMD_NET=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f1)
    CONF_MAC=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f2 | awk '{print tolower($0)}')
    CONF_IP=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f3)
    CONF_HOST=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f4)
    echo "${CONF_CMD_NET},${CONF_MAC},${CONF_IP},${CONF_HOST}" >>"${CONF_BUILD_FILE}"
    CONF_CURRENT=$(grep ${CONF_MAC} ${CONF_CURRENT_FILE})
    if [ $(echo -n ${CONF_CURRENT} | wc -w) -gt 0 ]; then
      if [ $(echo -n ${CONF_CURRENT} | grep -v ${CONF_IP} | wc -w) -gt 0 ] || [ $(echo -n ${CONF_CURRENT} | grep -v ${CONF_HOST} | wc -w) -gt 1 ]; then
        echo "Detected change in new and current config, deleting lease for [$CONF_HOST]"
        sed -i /".* ${CONF_MAC} .*"/d ${CONF_CURRENT_FILE}
        CONF_FLUSHED_LEASES="true"
      fi
    fi
  done <${CONF_SOURCE_FILE}
done
echo "wrote '${CONF_BUILD_FILE}':" && cat ${CONF_BUILD_FILE} && echo "---"

if [ ${CONF_FLUSHED_LEASES} == "true" ] || [ ! -f ${CONF_CUSTOM_FILE} ] || ! diff ${CONF_CUSTOM_FILE} ${CONF_BUILD_FILE}; then
  if dnsmasq --conf-dir=${CONF_BUILD_DIR} --test; then
    cp -rvf ${CONF_BUILD_FILE} ${CONF_CUSTOM_FILE}
    echo "applied new dnsmasq config"
    kill -9 $(cat /run/dnsmasq.pid) 2>/dev/null
    echo "killed and restarted dnsmasq"
  else
    echo "new dnsmasq config failed to parse, leaving old config in place"
  fi
else
  echo "no new dnsmasq config detected, leaving old config in place"
fi
