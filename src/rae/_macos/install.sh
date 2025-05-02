#!/bin/bash

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf .zprofile .zsh_history .zsh_sessions
rm -rf /Users/graham/.profile
cat <<EOF >/Users/graham/.bash_profile
# .bash_profile

printf '\e[?2004l'
tput rmam
# tput smam

export PS1='\u@\h:\w\$ '

export LC_ALL=C ls
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
alias ls='gls $LS_OPTIONS'

export DOCKER_CLI_HINTS=false
export BASH_SILENCE_DEPRECATION_WARNING=1
export PYTHONDONTWRITEBYTECODE=1

bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

alias edit="/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl"
alias grep="grep --line-buffered"
alias fab="fab -e"
alias dns-cache-flush="sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder"
alias ssh-copy-id='sshcopyid_func'
function sshcopyid_func() { cat ~/.ssh/id_rsa.pub | ssh $1 'mkdir .ssh ; cat >>.ssh/authorized_keys' ;}

export PYTHON_HOME="${HOME}/.conda/envs/python3"

export CARGO_HOME="${HOME}/.cargo"

export GOROOT="${HOME}/.conda/envs/go"
export GOPATH="${HOME}/.go"

export PATH=${GOROOT}/bin:${CARGO_HOME}/bin:${PYTHON_HOME}/bin:/Library/Conda/anaconda3/bin:/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

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

cat <<EOF >"/Users/graham/Library/Application Support/Sublime Text/Packages/User/Preferences.sublime-settings"
// Settings in here override those in "Default/Preferences.sublime-settings",
// and are overridden in turn by syntax-specific settings.
{
	"font_size": 16,
	"ignored_packages":	["Vintage",],
	"dictionary": "Packages/Language - English/en_GB.dic",
}
EOF
cat <<EOF >"/Users/graham/Library/Application Support/Sublime Text/Packages/User/Default (OSX).sublime-keymap"
[
	{ "keys": ["super+r"], "command": "show_panel", "args": {"panel": "replace", "reverse": false} },
	{ "keys": ["alt+a"], "command": "replace_all", "args": {"close_panel": true}, "context": [{"key": "panel", "operand": "replace"}, {"key": "panel_has_focus"}] },
]
EOF
