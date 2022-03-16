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
# Remove all unnecessary apps using Clean My Mac

################################################################################
# Init Environment
################################################################################
sudo passwd root
sudo sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
chsh -s /bin/bash

# Kiwi settings - notifcations
# Sublime settings - find/replace/text
# Docker settings


