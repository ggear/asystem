#!/bin/sh

################################################################################
# Settings
################################################################################
# Sharing -> Computer Name
# Sharing -> Remote Login
# Security & Privacy -> Firewall -> Off
# Security & Privacy -> File Vault -> Turn off
# Security & Privacy -> Use apple watch to unlock
# Security & Privacy -> Privacy -> Full Disk Access -> Terminal
# Dock & Menu Bar -> Automatically hide and show the Dock
# Displays -> More space
# Displays -> Nightshift -> Sunset to Sunrise
# Keyboard -> Key repeat
# Keyboard -> Delay until repeat
# Keyboard -> Shortcuts -> App Shortcuts -> Show Previous Tab
# Keyboard -> Shortcuts -> App Shortcuts -> Show Next Tab
# Sound -> Play sound on startup -> Off
# Sound -> Play user interface sounds -> Off
# Sound -> Alert volume -> 0
# Time Machine -> On
# Time Machine -> Options -> Ignore
#   ~/.m2
#   ~/.conda
#   ~/.docker
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
# Profiles -> When the shell exits -> Close the window
# Text -> Change -> SF Mono Regular 14
# Window -> Columns -> 200
# Window -> Rows -> 60

################################################################################
# Install Apps
################################################################################
# Install Calca from App Store
# Install Infuse from App Store
# Install WhatsApp from App Store
# Install Adblock Plus from App Store
# Install from https://dl.google.com/drive-file-stream/GoogleDrive.dmg
# Install from https://dl.devmate.com/com.macpaw.CleanMyMac4/CleanMyMacX.dmg
# Install from https://cdn.bjango.com/files/istatmenus6/istatmenus6.60.zip
# Install from https://download.sublimetext.com/sublime_text_build_4107_mac.zip
# Install from https://downloads.kiwiforgmail.com/kiwi/release/consumer/Kiwi+for+Gmail+Setup.dmg
# Install from https://mirror.aarnet.edu.au/pub/videolan/vlc/3.0.16/macosx/vlc-3.0.16-intel64.dmg
# Install from https://update-software.sonos.com/software/mac/mdcr/SonosDesktopController1341.dmg
# Install from https://github.com/newmarcel/KeepingYouAwake/releases/download/1.6.1/KeepingYouAwake-1.6.1.zip
# Remove all unnecessary apps using Clean My Mac

################################################################################
# Init Environment
################################################################################
sudo passwd root
sudo scutil --set HostName $HOSTNAME
sudo scutil --set LocalHostName $HOSTNAME
sudo scutil --set ComputerName $HOSTNAME
chsh -s /bin/bash

################################################################################
# Install Python
################################################################################
sudo rm -rf /Library/Conda && sudo mkdir -p /Library/Conda && sudo chmod 777 /Library/Conda
wget https://repo.anaconda.com/miniconda/Miniconda3-4.5.12-MacOSX-x86_64.sh
chmod +x Miniconda3-4.5.12-MacOSX-x86_64.sh
./Miniconda3-4.5.12-MacOSX-x86_64.sh -p /Library/Conda/anaconda2 -b
rm Miniconda3-4.5.12-MacOSX-x86_64.sh
conda config --set channel_priority false
conda config --append envs_dirs $HOME/.conda/envs
conda create -y -n python2 python=2.7.18
conda create -y -n python3 python=3.10

################################################################################
# Install Brew
################################################################################
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
