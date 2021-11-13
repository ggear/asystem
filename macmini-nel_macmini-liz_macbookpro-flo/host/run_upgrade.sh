#!/bin/sh

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt update
apt upgrade -y --without-new-pkgs
apt -y full-upgrade
apt -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""

################################################################################
# Update repos
################################################################################
cat <<EOF >/etc/apt/sources.list
deb http://deb.debian.org/debian bullseye main contrib non-free
#deb-src http://deb.debian.org/debian bullseye main contrib non-free

deb http://deb.debian.org/debian-security/ bullseye-security main contrib non-free
#deb-src http://deb.debian.org/debian-security/ bullseye-security main contrib non-free

deb http://deb.debian.org/debian bullseye-updates main contrib non-free
#deb-src http://deb.debian.org/debian bullseye-updates main contrib non-free

deb http://deb.debian.org/debian bullseye-backports main contrib non-free
#deb-src http://deb.debian.org/debian bullseye-backports main contrib non-free

deb [arch=amd64] http://download.docker.com/linux/debian bullseye stable
#deb-src [arch=amd64] http://download.docker.com/linux/debian bullseye stable

EOF

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt update
apt upgrade -y --without-new-pkgs
apt -y full-upgrade
apt -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""

################################################################################
# Install packages
################################################################################
PACKAGES=(
  ntfs-3g
  acl
  rsync
  vim
  rename
  curl
  fswatch
  netselect-apt
  smartmontools
  avahi-daemon
  net-tools
  htop
  mbpfan
  lm-sensors
  apt-transport-https
  ca-certificates
  gnupg-agent
  software-properties-common
  docker-ce
  docker-ce-cli
  containerd.io
  cifs-utils
  samba
  smbclient
)
apt-get install -y ${PACKAGES[@]}
INSTALLED="$(apt list 2>/dev/null | column -t | awk -F"/" '{print $1"\t"$2}' | awk '{print "  "$1"="$3""}' | grep -v Listing)"
echo "" && echo "Run script base package versions:"
for PACKAGE in ${PACKAGES[@]}; do
  echo "apt-get install -y --allow-downgrades "$(echo "${INSTALLED}" | grep " "${PACKAGE}"=")
done
echo ""
