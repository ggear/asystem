#!/bin/bash

################################################################################
# Install Brew Packages
################################################################################
HOMEBREW_PREFIX=/Library/Home/Homebrew /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
brew update
brew install \
  r \
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
  netcat \
  rustup \
  exiftool \
  poppler \
  telnet \
  poppler \
  rstudio \
  regclient \
  mosquitto \
  coreutils \
  bluesnooze \
  mpv \
  ffmpeg \
  mediainfo \
  mkvtoolnix \
  pkg-config \
  docker-slim \
  hudochenkov/sshpass/sshpass
brew upgrade
brew cleanup

################################################################################
# Install Python Packages
################################################################################
wget https://repo.anaconda.com/miniconda/Miniconda3-py312_24.5.0-0-MacOSX-arm64.sh && chmod +x Miniconda3-py312_24.5.0-0-MacOSX-arm64.sh && sudo ./Miniconda3-py312_24.5.0-0-MacOSX-arm64.sh -b -p /Library/Conda/anaconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh && chmod +x Miniconda3-latest-MacOSX-x86_64.sh && ./Miniconda3-latest-MacOSX-x86_64.sh -b -p /Library/Conda/anaconda3
chown -R graham:staff /Library/Conda/anaconda3
conda config --add channels conda-forge
conda config --set channel_priority strict
conda env list
conda remove -y -n python3 --all
conda create -y -n python3 python=3.12.7
pip install --upgrade --default-timeout=1000 \
  fabric \
  docker \
  requests \
  packaging \
  pathlib2
