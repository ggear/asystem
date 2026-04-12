#!/bin/bash

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf .zprofile .zsh_history .zsh_sessions
rm -rf /Users/graham/.profile
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE

################################################################################
# Shell
################################################################################
cat <<'EOF' >~/.bash_profile
# .bash_profile

ulimit -n 65536

[[ $- == *i* ]] && { printf '\e[?2004l'; tput rmam; }

export PS1='\u@\h:\w\$ '

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

export PROMPT_COMMAND='echo -ne "\033]0;${USER}@${HOSTNAME}: ${PWD}\007"; history -a; history -c; history -r'

[[ $- == *i* ]] && {
  bind '"\e[A":history-search-backward'
  bind '"\e[B":history-search-forward'
}

alias edit="/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl"
alias fab="fab -e"
alias dns-cache-flush="sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder"
alias ssh-copy-id="sshcopyid_func"

grep() { /usr/bin/grep --line-buffered "$@"; }
find() { /opt/homebrew/bin/gfind "$@"; }
function sshcopyid_func() { cat ~/.ssh/id_ed25519.pub | ssh $1 'mkdir -p .ssh; cat >>.ssh/authorized_keys'; }

export PATH="/opt/homebrew/sbin:/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

export PYENV_ROOT="${HOME}/.pyenv"
eval "$(pyenv init -)"

export GOENV_ROOT="${HOME}/.goenv"
export GOPATH="${HOME}/.go"
export GOBIN="${HOME}/.go/bin"
eval "$(goenv init -)"

export NVM_DIR="${HOME}/.nvm"
nvm() { unset -f nvm node npm npx; [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"; nvm "$@"; }
node() { unset -f nvm node npm npx; [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"; node "$@"; }
npm() { unset -f nvm node npm npx; [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"; npm "$@"; }
npx() { unset -f nvm node npm npx; [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"; npx "$@"; }

EOF

################################################################################
# SSH
################################################################################
cat <<'EOF' >~/.ssh/config
Host *
  WarnWeakCrypto no
  ServerAliveInterval 60
  ServerAliveCountMax 3
  AddKeysToAgent yes
  UseKeychain yes

Host github.com
  HostName ssh.github.com
  Port 443
  User git
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
EOF

################################################################################
# Git
################################################################################
cat <<'EOF' >~/.gitconfig
[user]
  name = Graham Gear
  email = graham@nowhere.com

[core]
  autocrlf = input
  editor = vim

[pull]
  rebase = true

[push]
  default = current
  autoSetupRemote = true

[fetch]
  prune = true

[rebase]
  autoStash = true

[diff]
  colorMoved = zebra

[merge]
  conflictstyle = diff3

[alias]
  sync = "!ssh -O check git@github.com 2>/dev/null || ssh -T git@github.com 2>/dev/null && git fetch"
  ssh = "!url=$(git remote get-url origin); echo $url | grep -q 'https://github.com' && git remote set-url origin git@github.com:$(echo $url | sed 's|https://github.com/||') || echo 'Already SSH'"
  undo = reset HEAD~1 --mixed
  unstage = reset HEAD --
EOF

################################################################################
# Ghostty
################################################################################
cat <<'EOF' >~/.config/ghostty/config
background = #000000
background-opacity = 1.0
unfocused-split-opacity = 1.0
split-divider-color = #000000

foreground = #c0caf5
cursor-color = #c0caf5

font-family = JetBrains Mono NL
font-size = 10

window-width = 287
window-height = 83

window-decoration = false
confirm-close-surface = false
EOF

################################################################################
# Python
################################################################################
PYENV_ROOT="${HOME}/.pyenv"
PYTHON_VERSION_LATEST=$(pyenv install --list | grep -E '^[[:space:]]*[0-9]+\.[0-9]+\.[1-9][0-9]*$' | tail -1 | tr -d ' ')
PYTHON_VERSION_LATEST=3.12.8
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
GO_VERSION_LATEST=1.25.8
chmod -R u+w ${GOENV_ROOT}/versions/*
for env in $(goenv versions --bare); do goenv uninstall -f "$env"; done
goenv install -sv "${GO_VERSION_LATEST}"
GOROOT="${GOENV_ROOT}/versions/${GO_VERSION_LATEST}"
goenv global "${GO_VERSION_LATEST}"
goenv versions
echo "$("${GOROOT}/bin/go" version) installed"

################################################################################
# Node
################################################################################
nvm install --lts
npm install -g yarn
