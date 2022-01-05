#!/bin/sh

################################################################################
# Normalise
################################################################################
rm -rf .zprofile .zsh_history .zsh_sessions
cat <<EOF >/Users/graham/.bash_profile
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

export PATH=${HOME}/.conda/envs/python2/bin:/Library/Conda/anaconda2/bin:/usr/local/sbin:/usr/local/bin:${PATH}

EOF
sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
mkdir -p /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chown graham /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chgrp staff /Users/graham/Backup /Users/graham/Code /Users/graham/Temp

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
