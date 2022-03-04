#!/bin/sh

CONF_SOURCE_DIR="/mnt/data/udm-dnsmasq/dhcp.dhcpServers"
CONF_CURRENT_FILE="/mnt/data/udapi-config/dnsmasq.lease"
CONF_CUSTOM_DIR="/run/dnsmasq.conf.d"
CONF_CUSTOM_FILE="${CONF_CUSTOM_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_FILES="${CONF_CUSTOM_DIR}/dhcp.dhcpServers"*"custom.conf"

rm -vf ${CONF_CUSTOM_FILES}
for CONF_SOURCE_FILE in ${CONF_SOURCE_DIR}-*Management*-custom.conf ${CONF_SOURCE_DIR}-*Unfettered*-custom.conf ${CONF_SOURCE_DIR}-*Isolated*-custom.conf; do
  cp -rvf ${CONF_SOURCE_FILE} ${CONF_CUSTOM_DIR}
  while read CONF_SOURCE_LINE; do
    CONF_CMD_NET=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f1)
    CONF_MAC=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f2 | awk '{print tolower($0)}')
    CONF_IP=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f3)
    CONF_HOST=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f4)
    echo "${CONF_CMD_NET},${CONF_MAC},${CONF_IP},${CONF_HOST}" >>"${CONF_CUSTOM_FILE}"
    # Disable killing current DHCP leases, just rely on rebooting clients to pick up new details
    #    sed -i /".* ${CONF_MAC} .*"/d ${CONF_CURRENT_FILE}
  done <${CONF_SOURCE_FILE}
done

kill -9 $(cat /run/dnsmasq.pid)
