#!/bin/bash

apt-get install -y avahi-daemon
cat <<'EOF' >/etc/avahi/avahi-daemon.conf
[server]
use-ipv6=no
allow-interfaces=eth0
[publish]
publish-hinfo=no
publish-workstation=no
[reflector]
enable-reflector=no
EOF
systemctl enable --now avahi-daemon
systemctl restart avahi-daemon.service
systemctl status avahi-daemon.service
