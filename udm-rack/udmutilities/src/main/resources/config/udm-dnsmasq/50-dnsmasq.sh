#!/bin/sh

# Add your DHCP reservations here
# Format: [network name],[mac],[ip]
# Find your network name by checking the names of the files under /run/dnsmasq.conf.d
reservations="net_LAN_br0_192-168-1-0-24,00:08:00:00:5b:08,192.168.1.5
              net_LAN_br0_192-168-1-0-24,00:09:23:00:8a:09,192.168.1.6
              net_VLAN_3     _br6_192-168-3-0-24,00:12:11:00:7b:1a,192.168.3.5"

conf="/run/dnsmasq.conf.d/custom_reservations.conf"
rm -f "$conf"

# Add each reservation to config and delete the current lease
for r in ${reservations}; do
  network=$(echo "$r" | cut -d',' -f1)
  mac=$(echo "$r" | cut -d',' -f2 | awk '{print tolower($0)}')
  ip=$(echo "$r" | cut -d',' -f3)
  host=$(echo "$r" | cut -d',' -f4)

  echo "dhcp-host=set:${network},${mac},${ip},${host}"

  #    echo "dhcp-host=set:${network},${mac},${ip},${host}" >> "$conf"
  #    sed -i /".* ${mac} .*"/d /mnt/data/udapi-config/dnsmasq.lease
done

#kill -9 $(cat /run/dnsmasq.pid)
