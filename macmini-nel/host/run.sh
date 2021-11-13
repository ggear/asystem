#!/bin/sh

################################################################################
# Packages (from update script)
################################################################################
apt-get install -y  ntfs-3g=1:2017.3.23AR.3-4+deb11u1
apt-get install -y  acl=2.2.53-10
apt-get install -y  rsync=3.2.3-4+deb11u1
apt-get install -y  vim=2:8.2.2434-3
apt-get install -y  rename=1.13-1
apt-get install -y  curl=7.74.0-1.3+b1
apt-get install -y  fswatch=1.14.0+repack-13
apt-get install -y  netselect-apt=0.3.ds1-29
apt-get install -y  smartmontools=7.2-1
apt-get install -y  avahi-daemon=0.8-5
apt-get install -y  net-tools=1.60+git20181103.0eebece-1
apt-get install -y  htop=3.0.5-7
apt-get install -y  mbpfan=2.2.1-1
apt-get install -y  lm-sensors=1:3.6.0-7
apt-get install -y  apt-transport-https=2.2.4
apt-get install -y  ca-certificates=20210119
apt-get install -y  gnupg-agent=2.2.27-2
apt-get install -y  software-properties-common=0.96.20.2-2.1
apt-get install -y  docker-ce=5:20.10.10~3-0~debian-buster
apt-get install -y  docker-ce-cli=5:20.10.10~3-0~debian-buster
apt-get install -y  containerd.io=1.4.11-1
apt-get install -y  cifs-utils=2:6.11-3.1
apt-get install -y  samba=2:4.13.13+dfsg-1~deb11u2
apt-get install -y  smbclient=2:4.13.13+dfsg-1~deb11u2

################################################################################
# Shell
################################################################################
if [ $(grep "history-search" /etc/bash.bashrc | wc -l) -eq 0 ]; then
  echo "" >>/etc/bash.bashrc
  echo "bind '\"\e[A\":history-search-backward'" >>/etc/bash.bashrc
  echo "bind '\"\e[B\":history-search-forward'" >>/etc/bash.bashrc
fi

################################################################################
# Display
################################################################################
[ -e /sys/class/backlight/gmux_backlight ] && echo 0 > /sys/class/backlight/gmux_backlight/brightness

################################################################################
# Volumes
################################################################################
vgdisplay
df -h /var
lvdisplay /dev/$(hostname)-vg/var
if [ $(lvdisplay /dev/$(hostname)-vg/var | grep "LV Size                30.00 GiB" | wc -l) -eq 0 ]; then
  lvextend -L30G /dev/$(hostname)-vg/var
  resize2fs /dev/$(hostname)-vg/var
fi
vgdisplay
df -h /var
lvdisplay /dev/$(hostname)-vg/var

################################################################################
# Utilities
################################################################################
if [ ! -d /usr/local/go ]; then
  mkdir /tmp/go && cd /tmp/go
  wget -q https://dl.google.com/go/go1.14.linux-amd64.tar.gz
  tar xvfz go1.14.linux-amd64.tar.gz
  mv go /usr/local/go
  ln -s /usr/local/go/bin/go /usr/local/bin/go
  cd && rm -rf /tmp/go
fi

################################################################################
# Network
################################################################################
cat <<EOF >/etc/avahi/avahi-daemon.conf
# See avahi-daemon.conf(5) for more information

[server]
use-ipv4=yes
use-ipv6=yes
ratelimit-interval-usec=1000000
ratelimit-burst=1000
cache-entries-max=0

[wide-area]
enable-wide-area=yes

[publish]
publish-hinfo=no
publish-workstation=no

[reflector]
enable-reflector=yes
reflect-ipv=no

[rlimits]
EOF

################################################################################
# Monitoring
################################################################################
sensors-detect --auto
cat <<EOF >/etc/mbpfan.conf
[general]
min_fan_speed = 1800
max_fan_speed = 5500
low_temp = 60
high_temp = 66
max_temp = 80
polling_interval = 1
EOF
curl https://raw.githubusercontent.com/linux-on-mac/mbpfan/49f544fd8d596fa13d5525a5b042eee311568c67/mbpfan.service -o /etc/systemd/system/mbpfan.service
systemctl enable mbpfan.service

################################################################################
# Docker
################################################################################
curl -sfsSL https://download.docker.com/linux/debian/gpg | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add -
add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
curl -sL "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
docker system prune --volumes -f 2>/dev/null
if [ $(grep "cdgroup_enable=memory swapaccount=1" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="cdgroup_enable=memory swapaccount=1"/' /etc/default/grub
  update-grub
fi

################################################################################
# Samba
################################################################################
if [ -e /dev/sdb ]; then
  systemctl start smbd
  systemctl enable smbd
else
  systemctl stop smbd
  systemctl disable smbd
fi
