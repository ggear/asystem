#!/bin/bash

################################################################################
# Settings
################################################################################

# Remote Login -> On
# Firewall -> Off
# File Vault -> Off
# Function Keys -> On (Use as standard)
# Apple Watch -> Off (Don't use apple watch to unlock)
# Full Disk Access -> Terminal
# Dock hide -> On
# Hot corners -> All off
# Key repeat -> Fast
# Delay until repeat -> Slow
# Keybaord navigation -> On
# Keyboard shortcuts -> App Shortcuts -> Show Previous Tab
# Keyboard shortcuts -> App Shortcuts -> Show Next Tab
# Extensions -> Share -> Reduce to minimal set
# Alert volume -> 0%
# Sounds effects -> Off
# Internet Accounts -> Google -> Calendars

################################################################################
# Safari
################################################################################
# Safari -> Downloads -> Desktop

################################################################################
# Terminal
################################################################################
# Profiles -> Shell -> When the shell exits -> Close the window
# Text -> Change -> SF Mono Regular 14
# Window -> Columns -> 325
# Window -> Rows -> 90
# Adavanced -> Audible Bell -> Off
# Keyboard functions keys

################################################################################
# Apps
################################################################################
# Install WhatsApp from App Store
# Install from https://www.office.com
# Install from https://dl.google.com/drive-file-stream/GoogleDrive.dmg
# Install from https://mirror.aarnet.edu.au/pub/videolan/vlc/3.0.16/macosx/vlc-3.0.16-intel64.dmg
# Install from https://update-software.sonos.com/software/mac/mdcr/SonosDesktopController1341.dmg
# Install from https://download-cdn.jetbrains.com/idea/ideaIU-2021.3.2.dmg

################################################################################
# Optional Apps
################################################################################
# Install Calca from App Store
# Install from https://dl.devmate.com/com.macpaw.CleanMyMac4/CleanMyMacX.dmg
# Install from https://cdn.bjango.com/files/istatmenus6/istatmenus6.60.zip
# Install from https://github.com/newmarcel/KeepingYouAwake/releases/download/1.6.1/KeepingYouAwake-1.6.1.zip

################################################################################
# Setup
################################################################################
HOSTNAME="macbook-rue"
sudo scutil --set ComputerName "$HOSTNAME"
sudo scutil --set HostName "$HOSTNAME"
sudo scutil --set LocalHostName "$HOSTNAME"
dscacheutil -flushcache

################################################################################
# Sublime
################################################################################
cat <<EOF >"/Users/graham/Library/Application Support/Sublime Text/Packages/User/Preferences.sublime-settings"
// Settings in here override those in "Default/Preferences.sublime-settings",
// and are overridden in turn by syntax-specific settings.
{
		"font_size": 16,
}
EOF
cat <<EOF >"/Users/graham/Library/Application Support/Sublime Text/Packages/User/Default (OSX).sublime-keymap"
[
	{ "keys": ["super+r"], "command": "show_panel", "args": {"panel": "replace", "reverse": false} },
	{ "keys": ["alt+a"], "command": "replace_all", "args": {"close_panel": true},
		 "context": [{"key": "panel", "operand": "replace"}, {"key": "panel_has_focus"}]
	},
]
EOF

################################################################################
# Shell
################################################################################
chsh -s /bin/bash

################################################################################
# SSH
################################################################################
sudo passwd root
sudo sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
vi /Users/graham/.ssh/.password
chmod 600 /Users/graham/.ssh/.password

################################################################################
# Git
################################################################################
git config --global credential.helper osxkeychain
git config --global user.name "Graham Gear"
git config --global user.email graham.gear@nowhere.org
git config --global advice.detachedHead false

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew upgrade

################################################################################
# ASystem
################################################################################
if [ ! -d ~/Code/asystem ]; then
  cd ~/Code
  git clone https://github.com/ggear/asystem.git
  cd asystem
  fab purge setup
fi
