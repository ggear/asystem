#!/bin/sh

################################################################################
# Install Brew Packages
################################################################################
brew update
brew install \
  htop \
  wget \
  watch \
  rename \
  ffmpeg \
  rustup \
  exiftool \
  pkg-config \
  poppler \
  telnet \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup

################################################################################
# Install Brew Packages
################################################################################
pip install \
  fabric
