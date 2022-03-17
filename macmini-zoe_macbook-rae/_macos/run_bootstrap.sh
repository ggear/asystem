#!/bin/sh

################################################################################
# Settings
################################################################################
# Sharing -> Computer Name
# Sharing -> Computer Name -> Edit
# Sharing -> Remote Login
# Security & Privacy -> Firewall -> Off
# Security & Privacy -> File Vault -> Turn off
# Security & Privacy -> Use apple watch to unlock
# Security & Privacy -> Privacy -> Full Disk Access -> Terminal
# Dock & Menu Bar -> Automatically hide and show the Dock
# Displays -> More space
# Displays -> Nightshift -> Sunset to Sunrise -> 75%
# Keyboard -> Key repeat -> 100%
# Keyboard -> Delay until repeat -> 80%
# Keyboard -> Shortcuts -> App Shortcuts -> Show Previous Tab
# Keyboard -> Shortcuts -> App Shortcuts -> Show Next Tab
# Sound -> Alert volume -> 0%
# Sound -> Play user interface sounds effects -> Off
# Sound -> Show sound in menu bar -> Always
# Time Machine -> Back automatically -> On
# Time Machine -> Show time machine in menu bar -> On
# Time Machine -> Options -> Ignore
#   ~/.conda
#   ~/Backup
#   ~/Code
#   ~/Music
#   ~/Temp

################################################################################
# Safari
################################################################################
# Safari -> Downloads -> Desktop

################################################################################
# Terminal
################################################################################
# Profiles -> Shell -> When the shell exits -> Close the window
# Text -> Change -> SF Mono Regular 14
# Window -> Columns -> 200
# Window -> Rows -> 60
# Adavanced -> Audible Bell -> Off

################################################################################
# Install Apps
################################################################################
# Install Calca from App Store
# Install Infuse from App Store
# Install WhatsApp from App Store
# Install from https://dl.google.com/drive-file-stream/GoogleDrive.dmg
# Install from https://dl.devmate.com/com.macpaw.CleanMyMac4/CleanMyMacX.dmg
# Install from https://cdn.bjango.com/files/istatmenus6/istatmenus6.60.zip
# Install from https://download.sublimetext.com/sublime_text_build_4107_mac.zip
# Install from https://downloads.kiwiforgmail.com/kiwi/release/consumer/Kiwi+for+Gmail+Setup.dmg
# Install from https://mirror.aarnet.edu.au/pub/videolan/vlc/3.0.16/macosx/vlc-3.0.16-intel64.dmg
# Install from https://update-software.sonos.com/software/mac/mdcr/SonosDesktopController1341.dmg
# Install from https://github.com/newmarcel/KeepingYouAwake/releases/download/1.6.1/KeepingYouAwake-1.6.1.zip
# Install from https://desktop.docker.com/mac/main/amd64/Docker.dmg
# Install from https://download-cdn.jetbrains.com/idea/ideaIU-2021.3.2.dmg
# Remove all unnecessary apps using Clean My Mac

################################################################################
# Init Environment
################################################################################
sudo passwd root
sudo sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
vi /Users/graham/.ssh/.password
chmod 600 /Users/graham/.ssh/.password
chsh -s /bin/bash
git config --global credential.helper osxkeychain
git config --global user.name "Graham Gear"
git config --global user.email graham.gear@nowhere.org

# Universal Controlh

# Kiwi settings - notifcations
# Sublime settings - find/replace/text
# Docker settings
# Office 365

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew upgrade

################################################################################
# Python
################################################################################
if [ ! -d /Library/Conda/anaconda2/bin/conda ]; then
  cd ~/Temp
  rm -rf /Library/Conda && mkdir -p /Library/Conda && chmod 777 /Library/Conda
  wget https://repo.anaconda.com/miniconda/Miniconda3-4.5.12-MacOSX-x86_64.sh
  chmod +x Miniconda3-4.5.12-MacOSX-x86_64.sh
  ./Miniconda3-4.5.12-MacOSX-x86_64.sh -p /Library/Conda/anaconda2 -b
  rm Miniconda3-4.5.12-MacOSX-x86_64.sh
  conda config --set channel_priority false
  conda config --append envs_dirs $HOME/.conda/envs
  conda create -y -n python2 python=2.7.18
  conda create -y -n python3 python=3.10
fi

################################################################################
# Asystem
################################################################################
if [ ! -d ~/Code/asystem ]; then
  brew install pkg-config poppler
  pip install fabric
  cd ~/Code
  git clone https://github.com/ggear/asystem.git
  cd asystem
  fab purge setup
fi
