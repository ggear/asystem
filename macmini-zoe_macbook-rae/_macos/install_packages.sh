#!/bin/sh

################################################################################
# Install Brew Packages
################################################################################
brew update
brew install \
  jq \
  htop \
  wget \
  watch \
  rename \
  ffmpeg \
  rustup \
  exiftool \
  poppler \
  telnet \
  mosquitto \
  pkg-config \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup

################################################################################
# Install Brew Packages
################################################################################
pip install \
  fabric
