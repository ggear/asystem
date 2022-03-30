#!/bin/bash

################################################################################
# Install packages
################################################################################
PACKAGES=(
  jq
  nut
  ntp
  ntfs-3g
  acl
  unrar
  rsync
  vim
  rename
  curl
  screen
  fswatch
  netselect-apt
  smartmontools
  avahi-daemon
  net-tools
  mbpfan
  lm-sensors
  apt-transport-https
  ca-certificates
  gnupg-agent
  software-properties-common
  mkvtoolnix
  docker-ce
  docker-ce-cli
  containerd.io
  cifs-utils
  samba
  cups
  smbclient
  inotify-tools
  htop
  iotop
  hdparm
  stress-ng
  memtester
  linux-cpupower
  firmware-realtek
  firmware-linux-nonfree
  hwinfo
  lshw
  vlan
  ffmpeg
  powertop
  libc6-i386
  intel-microcode
)
apt-get update
for PACKAGE in "${PACKAGES[@]}"; do
  apt-get install -y "${PACKAGE}"
done
INSTALLED="$(apt list 2>/dev/null | grep -v " i386" | column -t | awk -F"/" '{print $1"\t"$2}' | awk '{print "  "$1"="$3""}' | grep -v Listing)"
echo "" && echo "Run script base package versions:"
for PACKAGE in "${PACKAGES[@]}"; do
  PACKAGE_VERSION=$(echo "${INSTALLED}" | grep " "${PACKAGE}"=")
  echo "apt-get install -y --allow-downgrades '"${PACKAGE_VERSION##*( )}"'"
done
echo ""
