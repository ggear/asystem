#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

set -ex

################################################################################
# Modules
################################################################################
touch /etc/modprobe.d/blacklist-wifi.conf /etc/modprobe.d/blacklist-bluetooth.conf
sed -i '/^blacklist bcma-pci-bridge$/d' /etc/modprobe.d/blacklist-wifi.conf
grep -qxF 'blacklist bcma' /etc/modprobe.d/blacklist-wifi.conf || echo 'blacklist bcma' | tee -a /etc/modprobe.d/blacklist-wifi.conf
grep -qxF 'blacklist bluetooth' /etc/modprobe.d/blacklist-bluetooth.conf || echo 'blacklist bluetooth' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf
grep -qxF 'blacklist btusb' /etc/modprobe.d/blacklist-bluetooth.conf || echo 'blacklist btusb' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf
grep -qxF 'blacklist btbcm' /etc/modprobe.d/blacklist-bluetooth.conf || echo 'blacklist btbcm' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf
grep -qxF 'blacklist hci_uart' /etc/modprobe.d/blacklist-bluetooth.conf || echo 'blacklist hci_uart' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf
rm -f /etc/modprobe.d/blacklist-applesmc.conf
update-initramfs -u -k all

################################################################################
# Fan
################################################################################
if modinfo applesmc >/dev/null 2>&1; then
  apt-get install -y --allow-downgrades 'mbpfan=2.3.0-1+b1'
  echo applesmc | tee /etc/modules-load.d/applesmc.conf
  modprobe applesmc
  tee /etc/mbpfan.conf <<'EOT'
[general]
min_fan_speed = 1800
max_fan_speed = 4800
low_temp = 40
high_temp = 60
max_temp = 65
polling_interval = 1
EOT
  systemctl enable mbpfan.service
  systemctl restart mbpfan.service
fi

################################################################################
# Python
################################################################################
if [ ! -d /root/.pyenv/.git ]; then
  rm -rf /root/.pyenv
  git clone https://github.com/pyenv/pyenv.git /root/.pyenv
fi
(
  cd /root/.pyenv || exit 1
  if [ "$(git describe --tags 2>/dev/null)" != "v${ASYSTEM_PYENVBIN_VERSION}" ]; then
    git fetch --all --tags
    git checkout "v${ASYSTEM_PYENVBIN_VERSION}"
    ./src/configure && make -C src
  fi
)
ln -sf /root/.pyenv/libexec/pyenv /root/.pyenv/bin/pyenv
source /root/.bashrc
cd /tmp
if [ ! -d "/root/.pyenv/versions/${ASYSTEM_PYTHON_VERSION}/bin" ]; then
  pyenv install -s "${ASYSTEM_PYTHON_VERSION}"
  "/root/.pyenv/versions/${ASYSTEM_PYTHON_VERSION}/bin/pip" install --root-user-action ignore --default-timeout=1000 --upgrade pip
fi
find /root/.pyenv/versions -mindepth 1 -maxdepth 1 -type d ! -name "${ASYSTEM_PYTHON_VERSION}" -exec rm -rf {} +
