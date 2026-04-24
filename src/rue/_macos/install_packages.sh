#!/bin/bash

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew install --cask \
  vlc \
  plex \
  openra \
  ghostty \
  claude \
  claude-code \
  docker-desktop \
  google-drive \
  mqtt-explorer \
  google-chrome \
  sublime-text \
  keepingyouawake
brew install \
  pv \
  jq \
  yq \
  xq \
  rg \
  git \
  duf \
  nvm \
  pigz \
  mole \
  grep \
  bash \
  btop \
  htop \
  wget \
  shfmt \
  watch \
  skopeo \
  rename \
  goenv \
  gotestsum \
  pyenv \
  pyenv-virtualenv \
  netcat \
  rustup \
  exiftool \
  poppler \
  telnet \
  poppler \
  regclient \
  mosquitto \
  coreutils \
  findutils \
  mpv \
  ffmpeg \
  mediainfo \
  mkvtoolnix \
  pkg-config \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup
