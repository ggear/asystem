#!/bin/bash

################################################################################
# Brew
################################################################################
HOMEBREW_PREFIX=/Library/Home/Homebrew /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
brew update
brew install \
  pv \
  jq \
  yq \
  xq \
  duf \
  grep \
  bash \
  htop \
  wget \
  watch \
  skopeo \
  rename \
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
  bluesnooze \
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
