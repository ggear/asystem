#!/bin/bash

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew install --cask \
  openra \
  ghostty \
  claude \
  claude-code \
  docker-desktop \
  google-drive \
  mqtt-explorer \
  sublime-text
brew install \
  pv \
  jq \
  yq \
  xq \
  git \
  duf \
  nvm \
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
# Optional
brew install \
  bluesnooze

################################################################################
# NVM
################################################################################
nvm install --lts
npm install -g yarn