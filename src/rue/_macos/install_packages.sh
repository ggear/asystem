#!/bin/bash

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew install --cask \
  vlc \
  plex \
  claude \
  openra \
  ghostty \
  claude-code \
  google-drive \
  sublime-text \
  google-chrome \
  mqtt-explorer \
  docker-desktop \
  keepingyouawake
brew install \
  gh \
  jq \
  pv \
  rg \
  xq \
  yq \
  duf \
  git \
  mpv \
  nvm \
  bash \
  btop \
  grep \
  htop \
  just \
  mole \
  node \
  pigz \
  wget \
  goenv \
  pyenv \
  shfmt \
  watch \
  ffmpeg \
  netcat \
  poetry \
  rename \
  rustup \
  skopeo \
  telnet \
  poppler \
  poppler \
  exiftool \
  gotestsum \
  coreutils \
  findutils \
  mediainfo \
  mkvtoolnix \
  mosquitto \
  regclient \
  pkg-config \
  shellcheck \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup
