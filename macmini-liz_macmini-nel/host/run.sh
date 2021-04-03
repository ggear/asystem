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
  docker-ce=5:19.03.13~3-0~debian-buster \
  docker-ce-cli=5:19.03.13~3-0~debian-buster \
  containerd.io=1.3.7-1
curl -sL "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q)
docker system prune --volumes -f
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
cat <<EOF >/etc/samba/smb.conf
[global]
   workgroup = WORKGROUP
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   panic action = /usr/share/samba/panic-action %d
   server role = standalone server
   obey pam restrictions = yes
   unix password sync = yes
   passwd program = /usr/bin/passwd %u
   passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
   pam password change = yes
   map to guest = bad user
   usershare allow guests = yes

[media]
    comment = Media Files
    path = /data/media
    browseable = yes
    read only = no
    guest ok = yes
EOF
systemctl restart smbd

################################################################################
# Upgrade
#
# Generated by command:
# echo "DEBIAN_FRONTEND=noninteractive apt-get install -y \\" && apt list --upgradable 2>/dev/null | column -t | awk -F"/" '{print $1"\t"$2}' | awk '{print "  "$1"="$3" \\"}' | grep -v Listing && echo "&& apt -y autoremove"
#
################################################################################
