#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'mbpfan=2.2.1-1'

################################################################################
# Network
################################################################################
! grep 8021q /etc/modules >/dev/null && echo "8021q" | tee -a /etc/modules

################################################################################
# Fan
################################################################################
cat <<EOF >/etc/mbpfan.conf
[general]
min_fan_speed = 1800
max_fan_speed = 6500
low_temp = 40
high_temp = 60
max_temp = 65
polling_interval = 1
EOF
curl https://raw.githubusercontent.com/linux-on-mac/mbpfan/49f544fd8d596fa13d5525a5b042eee311568c67/mbpfan.service -o /etc/systemd/system/mbpfan.service
systemctl enable mbpfan.service
