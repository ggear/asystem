#!/bin/sh

################################################################################
# Install Brew Packages
################################################################################
brew update
brew install \
  pv \
  jq \
  grep \
  htop \
  wget \
  watch \
  rename \
  ffmpeg \
  netcat \
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
