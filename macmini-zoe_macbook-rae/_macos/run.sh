#!/bin/sh

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf .zprofile .zsh_history .zsh_sessions
cat <<EOF >/Users/graham/.bash_profile
# .bash_profile

export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
alias ls='ls $LS_OPTIONS'

bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

alias edit="/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl"
alias grep="grep --line-buffered"
alias fab="fab -e"

alias ssh-copy-id='sshcopyid_func'
function sshcopyid_func() { cat ~/.ssh/id_rsa.pub | ssh $1 'mkdir .ssh ; cat >>.ssh/authorized_keys' ;}

export PATH=/Users/graham/.conda/envs/python3/bin:/Library/Conda/anaconda2/bin:/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:${PATH}

EOF
cat <<EOF >/var/root/.profile
# .profile

export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
alias ls='ls $LS_OPTIONS'
EOF
mkdir -p /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chown graham /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chgrp staff /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
