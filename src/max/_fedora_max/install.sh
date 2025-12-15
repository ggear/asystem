#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

################################################################################
# Volumes
################################################################################
${SERVICE_INSTALL}/volumes.sh || exit 1

################################################################################
# mbpfan
################################################################################
dnf copr enable dperson/mbpfan
dnf install mbpfan
cat <<'EOF' >/etc/mbpfan.conf
[general]
low_temp = 55          # if temperature in celcius is below this, fans will run at minimum speed, default 63
high_temp = 60         # if temperature in celcius is above this, fan speed will gradually increase, default 66
max_temp = 80          # if temperature in celcius is above this, fans will run at maximum speed, default 86
polling_interval = 1   # seconds to poll, default 1
EOF
systemctl enable --now mbpfan
systemctl restart mbpfan
systemctl status mbpfan
