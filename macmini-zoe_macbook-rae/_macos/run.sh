#!/bin/sh

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

# Terminal
# - Profiles -> When the shell exits -> Close the window
# - Text -> Change -> SF Mono Regular 14
# - Window -> Columns -> 200
# - Window -> Rows -> 60

# Install Apps
# - Install Calca from App Store
# - Infuse from App Store
# - Adblock Plus from App Store
# - Install from https://dl.google.com/drive-file-stream/GoogleDrive.dmg
# - Install from https://dl.devmate.com/com.macpaw.CleanMyMac4/CleanMyMacX.dmg
# - Install from https://cdn.bjango.com/files/istatmenus6/istatmenus6.60.zip
# - Install from https://download.sublimetext.com/sublime_text_build_4107_mac.zip
# - Install from https://downloads.kiwiforgmail.com/kiwi/release/consumer/Kiwi+for+Gmail+Setup.dmg
# - Install from https://mirror.aarnet.edu.au/pub/videolan/vlc/3.0.16/macosx/vlc-3.0.16-intel64.dmg
# - Install from https://github.com/newmarcel/KeepingYouAwake/releases/download/1.6.1/KeepingYouAwake-1.6.1.zip
# - Remove all unnecessary apps using Clean My Mac

# Initialise
# sudo passwd root
# sudo scutil --set HostName <name>
# sudo scutil --set LocalHostName <name>
# sudo scutil --set ComputerName <name>

chsh -s /bin/bash
rm -rf .zprofile .zsh_history .zsh_sessions
cat <<EOF >~/.bash_profile
# .bash_profile

export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad

bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

alias edit="/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl"
alias grep="grep --line-buffered"
alias fab="fab -e"

alias ssh-copy-id='sshcopyid_func'
function sshcopyid_func() { cat ~/.ssh/id_rsa.pub | ssh $1 'mkdir .ssh ; cat >>.ssh/authorized_keys' ;}

export PATH=/opt/local/bin:/opt/local/sbin:/usr/sbin:$PATH
EOF
sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
mkdir -p ~/Backup ~/Code ~/Temp
git config --global user.name "Graham Gear"
git config --global user.email graham.gear@gmail.com
#! brew --help 1>&2 >/dev/null && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#brew update
#brew upgrade
#brew install \
#  htop \
#  wget \
#  watch
