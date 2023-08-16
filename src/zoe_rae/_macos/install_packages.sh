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
  poppler \
  mosquitto \
  pkg-config \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup

################################################################################
# Install Python Packages
################################################################################
#conda env list
#conda remove -y -n python3 --all
#conda create -y -n python3 python=3.11.4
pip install \
  fabric \
  docker \
  requests \
  packaging \
  pathlib2
