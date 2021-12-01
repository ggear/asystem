#!/bin/sh

# Allow host to stay up with lid closed: https://ubuntuhandbook.org/index.php/2020/05/lid-close-behavior-ubuntu-20-04/
# Disable descrete GPU and enable integrated GPU: https://github.com/0xbb/gpu-switch, think this is the go https://github.com/0xbb/apple_set_os.efi referencing https://unix.stackexchange.com/questions/193425/enabling-intel-iris-pro-syslinux-tails-system-macbook-pro-15-retina-late-2013
# Disable bluetooth (same as macmini?)
# Disable sound (same as macmini?)
# Disable wireless (same as macmini?)
# Check powertop
# Check boot log

################################################################################
# Display
################################################################################
if [ -e /sys/class/backlight/gmux_backlight ] && [ ! -f /etc/systemd/system/backlight.service ]; then
  cat <<EOF >/etc/systemd/system/backlight.service
[Unit]
Description=Turn backlight off
After=default.target
[Service]
ExecStart=/bin/sh -c '/usr/bin/echo 0 > /sys/class/backlight/gmux_backlight/brightness'
[Install]
WantedBy=default.target
EOF
  systemctl daemon-reload
  systemctl enable backlight.service
  systemctl start backlight.service
fi
