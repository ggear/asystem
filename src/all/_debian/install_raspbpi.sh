#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

set -ex

################################################################################
# System
################################################################################
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/turbowarp.gpg] https://releases.turbowarp.org/deb stable main" > /etc/apt/sources.list.d/turbowarp.list && wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /usr/share/keyrings/microsoft.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list && wget -qO- https://desktop.turbowarp.org/release-signing-key.gpg | gpg --dearmor --yes -o /usr/share/keyrings/turbowarp.gpg
apt update && apt upgrade -y && apt autoremove -y
apt install -y \
  git \
  gpg \
  wget \
  btop \
  code \
  snapd \
  iotop \
  flatpak \
  make \
  curl \
  turbowarp-desktop \
  ca-certificates \
  build-essential
systemctl enable --now snapd.socket
flatpak remote-add --if-not-exists --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak update --system -y

################################################################################
# Games
################################################################################
apt install -y fheroes2
snap install prismlauncher-alpo
snap install openra --channel=latest/beta
snap install hedgewars
