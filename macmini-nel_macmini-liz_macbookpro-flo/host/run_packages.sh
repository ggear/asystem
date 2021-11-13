#!/bin/sh

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
