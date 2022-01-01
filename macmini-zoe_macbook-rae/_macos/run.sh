#!/bin/sh

# Initialise
sudo passwd root
sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
chsh -s /bin/bash

# Home
mkdir -p ~/Backup ~/Code ~/Temp
cd ~/Code
git clone https://github.com/ggear/asystem.git

# Brew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew upgrade
brew install htop wget watch

# Settings
# - Sharing -> Computer Name
# - Sharing -> Remote Login
# - Time Machine -> On
# - Security & Privacy -> Firewall -> Off
# - Security & Privacy -> File Vault -> Turn off
# - Security & Privacy -> Use apple watch to unlock
# - Security & Privacy -> Privacy -> Full Disk Access -> Terminal
# - Dock & Menu Bar -> Automatically hide and show the Dock
# - Displays -> More space
# - Displays -> Nightshift -> Sunset to Sunrise
# - Keyboard -> Key repeat
# - Keyboard -> Delay until repeat
# - Keyboard -> Shortcuts -> App Shortcuts -> Show Previous Tab
# - Keyboard -> Shortcuts -> App Shortcuts -> Show Next Tab
# - Sound -> Play sound on startup -> Off
# - Sound -> Play user interface sounds -> Off
# - Sound -> Alert volume -> 0

# Safari
# - Safari -> Downloads -> Desktop

# Terminal Settings
# - Profiles -> When the shell exits -> Close the window
# - Text -> Change -> SF Mono Regular 14
# - Window -> Columns -> 200
# - Window -> Rows -> 60

# App Store
# - Calca
# - Infuse
# - Adblock Plus

# Applications
# Remove all uncessary apps

# Google Drive
# wget https://dl.google.com/drive-file-stream/GoogleDrive.dmg
mv ~/Google\ Drive ~/Drive

# CleanMyMac X
#wget https://dl.devmate.com/com.macpaw.CleanMyMac4/CleanMyMacX.dmg

# iStat Pro
#wget https://cdn.bjango.com/files/istatmenus6/istatmenus6.60.zip

# Sublime Text
#wget https://download.sublimetext.com/sublime_text_build_4107_mac.zip

# Kiwi for Gmail
#wget https://downloads.kiwiforgmail.com/kiwi/release/consumer/Kiwi+for+Gmail+Setup.dmg

# VLC Download
#wget https://mirror.aarnet.edu.au/pub/videolan/vlc/3.0.16/macosx/vlc-3.0.16-intel64.dmg

# Keep Awake
wget https://objects.githubusercontent.com/github-production-release-asset-2e65be/25431634/01e1ea7d-2c92-4d41-a48a-e10835771b8f?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIWNJYAX4CSVEH53A%2F20220101%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20220101T085745Z&X-Amz-Expires=300&X-Amz-Signature=cb696df80e60223a6df244ca28e72302d633b3c0b4ab8308f52955fdc0e9acd9&X-Amz-SignedHeaders=host&actor_id=0&key_id=0&repo_id=25431634&response-content-disposition=attachment%3B%20filename%3DKeepingYouAwake-1.6.1.zip&response-content-type=application%2Foctet-stream