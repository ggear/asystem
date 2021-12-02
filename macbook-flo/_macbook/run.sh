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
