#!/bin/bash

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf .zprofile .zsh_history .zsh_sessions
rm -rf /Users/graham/.profile
cat <<'EOF' >/Users/graham/.bash_profile
# .bash_profile

printf '\e[?2004l'
tput rmam
# tput smam

defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE

export PS1='\u@\h:\w\$ '

export LC_ALL=C ls
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS="--color=auto"
alias ls="gls ${LS_OPTIONS}"

export DOCKER_CLI_HINTS=false
export BASH_SILENCE_DEPRECATION_WARNING=1
export PYTHONDONTWRITEBYTECODE=1

export HISTSIZE=100000
export HISTFILESIZE=100000
export HISTFILE=~/.bash_history
bash_sync_history() { history -a; history -c; history -r; }

export PROMPT_COMMAND='echo -ne "\033]0;${USER}@${HOSTNAME}: ${PWD}\007" && bash_sync_history'
bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

alias edit="/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl"
alias grep="grep --line-buffered"
alias fab="fab -e"
alias find="gfind"
alias dns-cache-flush="sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder"
alias ssh-copy-id="sshcopyid_func"
function sshcopyid_func() { cat ~/.ssh/id_rsa.pub | ssh $1 'mkdir .ssh; cat >>.ssh/authorized_keys'; }

export PATH="/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

export PYENV_ROOT="${HOME}/.pyenv"
export PYTHON_HOME="${PYENV_ROOT}/versions/$(pyenv version --bare)"

export GOENV_ROOT="${HOME}/.goenv"
export GOROOT="${GOENV_ROOT}/versions/$(goenv version-name)"
export GOPATH="${HOME}/.go"
export GOBIN="${HOME}/.go/bin"

export PATH="${PYTHON_HOME}/bin:${GOPATH}/bin:${GOROOT}/bin:${PATH}"

EOF
cat <<'EOF' >/var/root/.profile
# .profile

printf '\e[?2004l'
tput rmam
# tput smam

export PS1='\u@\h:\w\$ '

export LC_ALL=C ls
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS="--color=auto"
alias ls="gls ${LS_OPTIONS}"

export PROMPT_COMMAND='echo -ne "\033]0;${USER}@${HOSTNAME}: ${PWD}\007"'
bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'
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

################################################################################
# Python
################################################################################
PYENV_ROOT="${HOME}/.pyenv"
PYTHON_VERSION_LATEST=$(pyenv install --list | grep -E '^[[:space:]]*[0-9]+\.[0-9]+\.[1-9][0-9]*$' | tail -1 | tr -d ' ')
for env in $(pyenv versions --bare); do pyenv uninstall -f "$env"; done
for venv in $(pyenv virtualenvs --bare); do pyenv virtualenv-delete -f "$venv"; done
pyenv install -sv "${PYTHON_VERSION_LATEST}"
PYTHON_HOME="${PYENV_ROOT}/versions/${PYTHON_VERSION_LATEST}"
"${PYTHON_HOME}/bin/pip" install --upgrade \
  pip \
  fabric \
  docker \
  varsubst \
  requests \
  pathlib2 \
  packaging
pyenv global "${PYTHON_VERSION_LATEST}"
pyenv versions
pyenv virtualenvs
echo "$("${PYTHON_HOME}/bin/python" --version) installed"

################################################################################
# Go
################################################################################
GOENV_ROOT="${HOME}/.goenv"
GO_VERSION_LATEST=$(goenv install --list | grep -E '^[[:space:]]*[0-9]+\.[0-9]+\.[1-9][0-9]*$' | tail -1 | tr -d ' ')
for env in $(goenv versions --bare); do goenv uninstall -f "$env"; done
goenv install -sv "${GO_VERSION_LATEST}"
GOROOT="${GOENV_ROOT}/versions/${GO_VERSION_LATEST}"
goenv global "${GO_VERSION_LATEST}"
goenv versions
echo "$("${GOROOT}/bin/go" version) installed"
