#!/bin/sh

CONF_SOURCE_DIR="/mnt/data/udm-dnsmasq/dhcp.dhcpServers"
CONF_CURRENT_FILE="/mnt/data/udapi-config/dnsmasq.lease"
CONF_CUSTOM_DIR="/run/dnsmasq.conf.d"
CONF_CUSTOM_FILE="${CONF_CUSTOM_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_FILES="${CONF_CUSTOM_DIR}/dhcp.dhcpServers"*"custom.conf"

rm -vf ${CONF_CUSTOM_FILES}
for CONF_SOURCE_FILE in $(ls ${CONF_SOURCE_DIR}-*Management*-custom.conf ${CONF_SOURCE_DIR}-*Unfettered*-custom.conf ${CONF_SOURCE_DIR}-*Isolated*-custom.conf 2>/dev/null); do
  while read CONF_SOURCE_LINE; do
    CONF_CMD_NET=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f1)
    CONF_MAC=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f2 | awk '{print tolower($0)}')
    CONF_IP=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f3)
    CONF_HOST=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f4)
    echo "${CONF_CMD_NET},${CONF_MAC},${CONF_IP},${CONF_HOST}" >>"${CONF_CUSTOM_FILE}"
    CONF_CURRENT=$(grep ${CONF_MAC} ${CONF_CURRENT_FILE})
    if [ $(echo -n ${CONF_CURRENT} | wc -w) -gt 0 ]; then
      if [ $(echo -n ${CONF_CURRENT} | grep -v ${CONF_IP} | wc -w) -gt 0 ] || [ $(echo -n ${CONF_CURRENT} | grep -v ${CONF_HOST} | wc -w) -gt 1 ]; then
        echo "Detected change in new and current config, deleting lease for [$CONF_HOST]"
        sed -i /".* ${CONF_MAC} .*"/d ${CONF_CURRENT_FILE}
      fi
    fi
  done <${CONF_SOURCE_FILE}
done

if [ $(dnsmasq --conf-dir=/run/dnsmasq.conf.d --test) ]; then
  rm -vf ${CONF_CUSTOM_FILES}
fi
kill -9 $(cat /run/dnsmasq.pid)
