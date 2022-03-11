#!/bin/sh

################################################################################
# Display (enable)
################################################################################
#rm -rf /etc/modprobe.d/blacklist-video.conf
#gpu-switch -d

################################################################################
# Display (disable)
################################################################################
if [ ! -f /usr/sbin/gpu-switch ]; then
  wget https://raw.githubusercontent.com/0xbb/gpu-switch/master/gpu-switch -O /usr/sbin/gpu-switch
  chmod +x /usr/sbin/gpu-switch
  gpu-switch -i
fi

################################################################################
# Lid
################################################################################
sed -i 's/#HandleLidSwitch=suspend/HandleLidSwitch=ignore/g' /etc/systemd/logind.conf
sed -i 's/#HandleLidSwitchExternalPower=suspend/HandleLidSwitchExternalPower=ignore/g' /etc/systemd/logind.conf
systemctl restart systemd-logind.service

################################################################################
# Network
################################################################################
for VLAN in 4 6; do
  if ifconfig lan0 >/dev/null && [ $(grep "lan0.${VLAN}" /etc/network/interfaces | wc -l) -eq 0 ]; then
    cat <<EOF >>/etc/network/interfaces

auto lan0.${VLAN}
iface lan0.${VLAN} inet dhcp
    hwaddress ether ${VLAN}a:e0:4c:68:06:a1
EOF
  fi
  ifconfig "lan0.${VLAN}"
done
