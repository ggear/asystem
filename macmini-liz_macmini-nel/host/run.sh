#!/bin/sh

################################################################################
# Setup system
################################################################################
# Debian 10 (buster amd64 net iso)
# Install (non-graphical)
# Dont load proprietary media
# Set host to macmini-*.janeandgraham.com
# Create user graham
# Guided entire disk and setup LVM create partitions at 450GB, /tmp, /var, /home, max, force UEFI
# Install SSH server, standard sys utils
# Enable remote root login : /etc/ssh/sshd_config PermitRootLogin yes
# Second HDD (1.9TB), single partition with defaults (fdisk /dev/sdb) and formatted as ext4 (mkfs.ext4 /dev/sdb1)

################################################################################
# Shell
################################################################################
if [ $(grep "history-search" /etc/bash.bashrc | wc -l) -eq 0 ]; then
  echo "" >>/etc/bash.bashrc
  echo "bind '\"\e[A\":history-search-backward'" >>/etc/bash.bashrc
  echo "bind '\"\e[B\":history-search-forward'" >>/etc/bash.bashrc
fi

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
if [ -e /dev/sdb ] && [ $(grep "/dev/sdb1 /data ext4 defaults 1 2" /etc/fstab | wc -l) -eq 0 ]; then
  echo "/dev/sdb1 /data ext4 defaults 1 2" >>/etc/fstab
  mkdir -p /data
  mount -a
fi

################################################################################
# Utilities
################################################################################
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  rsync=3.1.3-6 \
  vim=2:8.1.0875-5 \
  curl=7.64.0-4+deb10u2 \
  fswatch=1.14.0+repack-8
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
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  smartmontools=6.6-1 \
  avahi-daemon=0.7-4+deb10u1 \
  net-tools=1.60+git20180626.aebd88e-1
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
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  htop=2.2.0-1+b1 \
  mbpfan=2.0.2-1 \
  lm-sensors=1:3.5.0-3
sensors-detect --auto
cat <<EOF >/etc/mbpfan.conf
[general]
min_fan_speed = 1800
max_fan_speed = 5500
low_temp = 60
high_temp = 66
max_temp = 80
polling_interval = 7
EOF
curl https://raw.githubusercontent.com/linux-on-mac/mbpfan/49f544fd8d596fa13d5525a5b042eee311568c67/mbpfan.service -o /etc/systemd/system/mbpfan.service
systemctl enable mbpfan.service

################################################################################
# Docker
################################################################################
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  apt-transport-https=1.8.2.2 \
  ca-certificates=20200601~deb10u2 \
  gnupg-agent=2.2.12-1+deb10u1 \
  software-properties-common=0.96.20.2-2
curl -sfsSL https://download.docker.com/linux/debian/gpg | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add -
add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
apt-get install -y \
  docker-ce=5:20.10.5~3-0~debian-buster \
  docker-ce-cli=5:20.10.5~3-0~debian-buster \
  containerd.io=1.4.4-1
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
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  cifs-utils=2:6.8-2 \
  samba=2:4.9.5+dfsg-5+deb10u1 \
  smbclient=2:4.9.5+dfsg-5+deb10u1
if [ -e /dev/sdb ]; then
  systemctl start smbd
  systemctl enable smbd
else
  systemctl stop smbd
  systemctl disable smbd
fi

################################################################################
# Upgrade
#
# Generated by command:
# apt list --upgradable 2>/dev/null | column -t | awk -F"/" '{print $1"\t"$2}' | awk '{print "  "$1"="$3" \\"}' | grep -v Listing
#
################################################################################
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  apt-utils=1.8.2.2 \
  apt=1.8.2.2 \
  base-files=10.3+deb10u9 \
  bind9-host=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  debian-archive-keyring=2019.1+deb10u1 \
  distro-info-data=0.41+deb10u3 \
  exim4-base=4.92-8+deb10u5 \
  exim4-config=4.92-8+deb10u5 \
  exim4-daemon-light=4.92-8+deb10u5 \
  file=1:5.35-4+deb10u2 \
  groff-base=1.22.4-3+deb10u1 \
  grub-common=2.02+dfsg1-20+deb10u4 \
  grub-efi-amd64-bin=2.02+dfsg1-20+deb10u4 \
  grub-efi-amd64-signed=1+2.02+dfsg1+20+deb10u4 \
  grub-efi-amd64=2.02+dfsg1-20+deb10u4 \
  grub2-common=2.02+dfsg1-20+deb10u4 \
  iproute2=4.20.0-2+deb10u1 \
  iputils-ping=3:20180629-2+deb10u2 \
  krb5-locales=1.17-3+deb10u1 \
  libapt-inst2.0=1.8.2.2 \
  libapt-pkg5.0=1.8.2.2 \
  libavahi-common-data=0.7-4+deb10u1 \
  libavahi-common3=0.7-4+deb10u1 \
  libavahi-core7=0.7-4+deb10u1 \
  libbind9-161=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libbsd0=0.9.1-2+deb10u1 \
  libcurl3-gnutls=7.64.0-4+deb10u2 \
  libdns-export1104=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libdns1104=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libefiboot1=37-2+deb10u1 \
  libefivar1=37-2+deb10u1 \
  libfreetype6=2.9.1-3+deb10u2 \
  libgnutls-dane0=3.6.7-4+deb10u6 \
  libgnutls30=3.6.7-4+deb10u6 \
  libgssapi-krb5-2=1.17-3+deb10u1 \
  libisc-export1100=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libisc1100=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libisccc161=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libisccfg163=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libk5crypto3=1.17-3+deb10u1 \
  libkrb5-3=1.17-3+deb10u1 \
  libkrb5support0=1.17-3+deb10u1 \
  libldap-2.4-2=2.4.47+dfsg-3+deb10u6 \
  libldap-common=2.4.47+dfsg-3+deb10u6 \
  liblwres161=1:9.11.5.P4+dfsg-5.1+deb10u3 \
  libmagic-mgc=1:5.35-4+deb10u2 \
  libmagic1=1:5.35-4+deb10u2 \
  libmariadb3=1:10.3.27-0+deb10u1 \
  libnss-systemd=241-7~deb10u7 \
  libp11-kit0=0.23.15-2+deb10u1 \
  libpam-systemd=241-7~deb10u7 \
  libpython3.7-minimal=3.7.3-2+deb10u3 \
  libpython3.7-stdlib=3.7.3-2+deb10u3 \
  libsqlite3-0=3.27.2-3+deb10u1 \
  libssl1.1=1.1.1d-0+deb10u6 \
  libsystemd0=241-7~deb10u7 \
  libudev1=241-7~deb10u7 \
  libxml2=2.9.4+dfsg1-7+deb10u1 \
  libzstd1=1.3.8+dfsg-3+deb10u2 \
  linux-compiler-gcc-8-x86=4.19.181-1 \
  linux-headers-amd64=4.19+105+deb10u11 \
  linux-image-amd64=4.19+105+deb10u11 \
  linux-kbuild-4.19=4.19.181-1 \
  linux-libc-dev=4.19.181-1 \
  mariadb-common=1:10.3.27-0+deb10u1 \
  openssl=1.1.1d-0+deb10u6 \
  python-apt-common=1.8.4.3 \
  python3-apt=1.8.4.3 \
  python3.7-minimal=3.7.3-2+deb10u3 \
  python3.7=3.7.3-2+deb10u3 \
  sudo=1.8.27-1+deb10u3 \
  systemd-sysv=241-7~deb10u7 \
  systemd=241-7~deb10u7 \
  tzdata=2021a-0+deb10u1 \
  udev=241-7~deb10u7 &&
  apt -y autoremove
