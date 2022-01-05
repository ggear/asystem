#!/bin/sh

################################################################################
# Install Brew Packages
################################################################################
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew upgrade
brew install \
  htop \
  wget \
  watch
