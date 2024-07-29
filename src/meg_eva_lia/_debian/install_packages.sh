#!/bin/bash

################################################################################
# Install packages
################################################################################
PACKAGES=(
  jq
  xq
  duf
  ntp
  psmisc
  usbutils
  dnsutils
  ntpdate
  ntfs-3g
  acl
  unrar
  rsync
  vim
  rename
  parted
  curl
  screen
  fswatch
  util-linux
  mediainfo
  digitemp
  tuptime
  bsdmainutils
  netselect-apt
  smartmontools
  avahi-daemon
  avahi-utils
  net-tools
  ethtool
  lm-sensors
  efivar
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
  firmware-linux-nonfree
  hwinfo
  lshw
  vlan
  powertop
  locales
  python3
  python3-pip
  tesseract-ocr
  libedgetpu1-std
  exfatprogs
  build-essential
  automake
  autoconf
  checkinstall
  libtool
  pkg-config
  intltool
  yasm
  nasm
  ruby-full
  xz-utils
  tk-dev
  zlib1g-dev
  llvm
  libssl-dev
  libbz2-dev
  libreadline-dev
  libsqlite3-dev
  libncurses5-dev
  libncursesw5-dev
  libffi-dev
  liblzma-dev
  libxml2-dev
  libgtk2.0-dev
  libnotify-dev
  libglib2.0-dev
  libevent-dev
  libcurl4-openssl-dev
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
