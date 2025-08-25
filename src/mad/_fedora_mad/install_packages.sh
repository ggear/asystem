#!/bin/bash

set -e

dnf install --refresh -y epel-release
dnf copr enable -y packager/duf
dnf copr enable -y packager/fswatch
dnf upgrade --refresh -y

ASYSTEM_PACKAGES_DNF=(
  jq
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
group_packages=$(dnf groupinfo "Development Tools" |
  awk '/Mandatory Packages:/,/Description:/{if ($1 ~ /^[a-zA-Z0-9]/) print $1}' |
  sort -u)
ASYSTEM_PACKAGES_DNF+=("${group_packages[@]}")
dnf install --refresh -y "${ASYSTEM_PACKAGES_DNF[@]}"

ASYSTEM_PACKAGES_PIP=(
  yq
)
pip3 install --upgrade --user "${ASYSTEM_PACKAGES_PIP[@]}"

for _package in "${ASYSTEM_PACKAGES_DNF[@]}"; do apt-get install -y "${_package}"; done
echo "#######################################################################################"
echo "Base image install commands:"
echo "#######################################################################################" && echo ""
for _package in "${ASYSTEM_PACKAGES_DNF[@]}"; do echo "install --refresh -y " "${_package}="$(dnf info "${_package}" 2>/dev/null | awk '/^Version/ {print $3}'); done
for _package in "${ASYSTEM_PACKAGES_PIP[@]}"; do echo "pip3 install --upgrade --user " "${_package}=="$(pip3 show {_package} 2>/dev/null | awk '/^Version:/ {print $2}'); done
echo "" && echo "#######################################################################################"
