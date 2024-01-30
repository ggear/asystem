#!/bin/bash
# shellcheck disable=SC2045

CONF_FLUSHED_LEASES="false"
CONF_SOURCE_FILE_PREFIX="/data/udm-dnsmasq/dhcp.dhcpServers"
CONF_CURRENT_FILE="/data/udapi-config/dnsmasq.lease"
CONF_BUILD_DIR="/tmp/dnsmasq.conf.d_tmp"
CONF_BUILD_FILE="${CONF_BUILD_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_DIR="/run/dnsmasq.conf.d"
CONF_CUSTOM_FILE="${CONF_CUSTOM_DIR}/dhcp.dhcpServers-custom.conf"
CONF_CUSTOM_FILES="dhcp.dhcpServers"*"custom.conf"

rm -rf ${CONF_BUILD_DIR}
cp -rvf ${CONF_CUSTOM_DIR} ${CONF_BUILD_DIR}
rm -rf "${CONF_BUILD_DIR}/${CONF_CUSTOM_FILES}"
for CONF_SOURCE_FILE in $(ls \
  ${CONF_SOURCE_FILE_PREFIX}-*Default*-custom.conf \
  ${CONF_SOURCE_FILE_PREFIX}-*Unfettered*-custom.conf \
  ${CONF_SOURCE_FILE_PREFIX}-*Controlled*-custom.conf \
  ${CONF_SOURCE_FILE_PREFIX}-*Isolated*-custom.conf \
  2>/dev/null); do
  while read -r CONF_SOURCE_LINE; do
    CONF_MAC=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f1 | cut -d'=' -f2 | awk '{print tolower($0)}')
    CONF_IP=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f2)
    CONF_HOST=$(echo "${CONF_SOURCE_LINE}" | cut -d',' -f3)
    if [ -z "${CONF_HOST}" ]; then
      CONF_HOST=${CONF_IP}
      CONF_IP=""
    fi
    CONF_BUILD="dhcp-host=${CONF_MAC},${CONF_IP},${CONF_HOST}"
    CONF_CURRENT=$(grep "${CONF_MAC}" "${CONF_CURRENT_FILE}")
    echo "${CONF_BUILD}" >>"${CONF_BUILD_FILE}"
    if [ "$(echo -n "${CONF_CURRENT}" | wc -w)" -gt 0 ]; then
      if [ -n "${CONF_IP}" ]; then
        if [ "$(echo -n "${CONF_CURRENT}" | grep -v "${CONF_IP}" | wc -w)" -gt 0 ] ||
          [ "$(echo -n "${CONF_CURRENT}" | grep -v "${CONF_HOST}" | wc -w)" -gt 1 ]; then
          echo "Host [${CONF_HOST}] with MAC [${CONF_MAC}] and IP [${CONF_IP}] config metadata and DHCP lease out of sync, flushing lease"
          sed -i /".* ${CONF_MAC} .*"/d ${CONF_CURRENT_FILE}
          CONF_FLUSHED_LEASES="true"
        else
          echo "Host [${CONF_HOST}] with MAC [${CONF_MAC}] and IP [${CONF_IP}] config metadata and DHCP lease in sync"
        fi
      else
        echo "Host [${CONF_HOST}] with MAC [${CONF_MAC}] config metadata and DHCP lease in sync"
      fi
    else
      echo "Host [${CONF_HOST}] with MAC [${CONF_MAC}] and IP [${CONF_IP}] config metadata found but no DHCP lease"
    fi
  done <"${CONF_SOURCE_FILE}"
done
if [ -f "${CONF_SOURCE_FILE_PREFIX}-aliases.conf" ]; then
  cat "${CONF_SOURCE_FILE_PREFIX}-aliases.conf" >>${CONF_BUILD_FILE}
fi
echo "wrote '${CONF_BUILD_FILE}':" && cat ${CONF_BUILD_FILE} && echo "---"

if [ ${CONF_FLUSHED_LEASES} == "true" ] || [ ! -f ${CONF_CUSTOM_FILE} ] ||
  ! diff ${CONF_CUSTOM_FILE} ${CONF_BUILD_FILE}; then
  if dnsmasq --conf-dir=${CONF_BUILD_DIR} --test; then
    cp -rvf ${CONF_BUILD_FILE} ${CONF_CUSTOM_FILE}
    echo "applied new dnsmasq config"
    kill -9 "$(cat /run/dnsmasq.pid)" 2>/dev/null
    echo "killed and restarted dnsmasq"
  else
    echo "new dnsmasq config failed to parse, leaving old config in place"
  fi
else
  echo "no new dnsmasq config detected, leaving old config in place"
fi

# INFO: Disable podman services since it has been deprecated since udm-pro-3
#killall -9 dhcp 2>/dev/null
#rm -f /run/cni/dhcp.sock
#/opt/cni/bin/dhcp daemon >/dev/null &
