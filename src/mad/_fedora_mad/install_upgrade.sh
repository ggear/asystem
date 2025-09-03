#!/bin/bash

################################################################################
# Upgrade
################################################################################
CURRENT_RELEASE=$(sed -n 's/.*release[[:space:]]\+\([0-9]\+\).*/\1/p' /etc/fedora-release)
LATEST_RELEASE=$(curl -s -L https://fedoraproject.org/releases.json | jq -r '[.[].version|select(test("^[0-9]+$"))]|max')
dnf-3 upgrade --refresh -y
echo "" && echo "#######################################################################################"
if [ "$CURRENT_RELEASE" -eq "$LATEST_RELEASE" ]; then
  echo "Current Fedora release [${CURRENT_RELEASE}] is already the latest, no upgrade required"
elif [ "$CURRENT_RELEASE" -lt "$LATEST_RELEASE" ]; then
  echo "Current Fedora release [${CURRENT_RELEASE}] will be upgraded to latest [${LATEST_RELEASE}]"
  dnf-3 system-upgrade download --releasever=${LATEST_RELEASE} --allowerasing
  dnf-3 upgrade --refresh -y
  dnf-3 autoremove -y
fi
echo "#######################################################################################" && echo ""
dnf-3 install -y dnf-plugins-core
dnf-3 config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
dnf-3 upgrade --refresh -y

################################################################################
# Packages
################################################################################
ASYSTEM_PACKAGES_DNF=(
  jq
  yq
  nvme-cli
  acl
  parted
  util-linux
  usbutils
  smartmontools
  htop
  iotop
  ethtool
  lm_sensors
  efivar
  cifs-utils
  samba
  samba-client
  cups
  avahi
  inotify-tools
  powertop
  python3
  python3-pip
  vim
  nano
  screen
  tmux
  curl
  wget
  unrar
  rsync
  mediainfo
  tesseract
  exfatprogs
  ntfs-3g
  mkvtoolnix
  ruby
  xz
  tk-devel
  llvm
  docker-ce
  docker-ce-cli
  containerd.io
  libcurl-devel
  libxml2-devel
  glib2-devel
  gtk2-devel
  libnotify-devel
  libevent-devel
  openssl-devel
  zlib-devel
  bzip2-devel
  readline-devel
  sqlite-devel
  ncurses-devel
  libffi-devel
  xz-devel
  autoconf
  automake
  libtool
  pkgconfig
  yasm
  nasm
  net-tools
  bind-utils
  b3sum
  fd-find
  fzf
  digitemp
  tuptime
  duf
  fswatch
)
group_packages=$(dnf-3 groupinfo "Development Tools" 2>/dev/null | grep "   " | sort -u)
ASYSTEM_PACKAGES_DNF+=($group_packages)
dnf-3 install -y "${ASYSTEM_PACKAGES_DNF[@]}"
echo "" && echo "#######################################################################################"
echo "Base image install commands:"
echo "#######################################################################################" && echo ""
for _package in "${ASYSTEM_PACKAGES_DNF[@]}"; do
  echo "dnf-3 install -y ${_package}-"$(dnf info "${_package}" 2>/dev/null | awk '/^Version/ {print $3}')
done
echo "" && echo "#######################################################################################"
