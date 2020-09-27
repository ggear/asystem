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

################################################################################
# Volumes
################################################################################
vgdisplay
df -h /var
lvdisplay /dev/macmini-liz-vg/var
if [ $(lvdisplay /dev/macmini-liz-vg/var | grep "LV Size                30.00 GiB" | wc -l) -eq 0 ]; then
  lvextend -L30G /dev/macmini-liz-vg/var
  resize2fs /dev/macmini-liz-vg/var
fi
vgdisplay
df -h /var
lvdisplay /dev/macmini-liz-vg/var

################################################################################
# Utilities
################################################################################
apt-get update
apt-get install -y \
  vim=2:8.1.0875-5 \
  curl=7.64.0-4+deb10u1 \
  fswatch=1.14.0+repack-8 \
  net-tools=1.60+git20180626.aebd88e-1
mkdir /tmp/go && cd /tmp/go
wget https://dl.google.com/go/go1.14.linux-amd64.tar.gz
tar xvfz go1.14.linux-amd64.tar.gz
mv go /usr/local/go
cd && rm -rf /tmp/go

################################################################################
# Network
################################################################################
apt-get install -y \
  avahi-daemon=0.7-4+b1
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
apt-get install -y \
  htop=2.2.0-1+b1 \
  lm-sensors=1:3.5.0-3
sensors-detect --auto

################################################################################
# Docker
################################################################################
apt-get install -y \
  apt-transport-https=1.8.2.1 \
  ca-certificates=20200601~deb10u1 \
  gnupg-agent=2.2.12-1+deb10u1 \
  software-properties-common=0.96.20.2-2
curl -sfsSL https://download.docker.com/linux/debian/gpg | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add -
add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
apt-get install -y \
  docker-ce=5:19.03.12~3-0~debian-buster \
  docker-ce-cli=5:19.03.12~3-0~debian-buster \
  containerd.io=1.2.13-2
curl -sL "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q)
docker system prune --volumes -f
