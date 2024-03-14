#!/bin/bash

if ! diff -q /root/install/udmutilities/latest/config/udm-certificates/.key.pem /data/unifi-core/config/unifi-core.key &>/dev/null ||
  ! diff -q /root/install/udmutilities/latest/config/udm-certificates/certificate.pem /data/unifi-core/config/unifi-core.crt &>/dev/null; then
  echo -n "Installing latest certificates ..."
  cp -uvf /root/install/udmutilities/latest/config/udm-certificates/.key.pem /data/unifi-core/config/unifi-core.key >/dev/null
  cp -uvf /root/install/udmutilities/latest/config/udm-certificates/certificate.pem /data/unifi-core/config/unifi-core.crt >/dev/null
  echo "done"
  echo -n "Restarting UniFi ..."
  systemctl restart unifi-core
  echo "done"
fi
