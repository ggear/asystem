#!/bin/bash

if [ "$(id -u)" -eq 0 ]; then
  INSTALL_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  cd / || exit 1
  exec sudo -u graham -H /bin/bash "${INSTALL_SCRIPT}" "$@"
fi
if [ "$(id -un)" != "graham" ]; then
  echo "install must run as [graham] or root, not [$(id -un)]" >&2
  exit 1
fi

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "${INSTALL_DIR}/.env"
export PATH="/opt/homebrew/sbin:/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${HOME}" || exit 1

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf ~/.zprofile ~/.zsh_history ~/.zsh_sessions
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

alias edit='/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl'
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

[[ $- == *i* ]] && [ -r /opt/homebrew/etc/bash_completion ] && . /opt/homebrew/etc/bash_completion
[[ $- == *i* ]] && command -v amedia >/dev/null && eval "$(amedia completion 2>/dev/null)"

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
  autocrlf = false
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
mkdir -p ~/.config/ghostty
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
PYTHON_VERSION_LATEST="${ASYSTEM_PYTHON_VERSION}"
for venv in $(pyenv virtualenvs --bare --skip-aliases); do
  [[ "${venv}" == "${PYTHON_VERSION_LATEST}/envs/"* ]] || pyenv virtualenv-delete -f "${venv}"
done
for env in $(pyenv versions --bare --skip-aliases --skip-envs); do
  [ "${env}" = "${PYTHON_VERSION_LATEST}" ] || pyenv uninstall -f "${env}"
done
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
GO_VERSION_LATEST="${ASYSTEM_GO_VERSION}"
for env in "${GOENV_ROOT}"/versions/*; do
  [ -d "${env}" ] && [ "${env##*/}" != "${GO_VERSION_LATEST}" ] && chmod -R u+w "${env}" && rm -rf "${env}"
done
goenv install -s "${GO_VERSION_LATEST}"
GOROOT="${GOENV_ROOT}/versions/${GO_VERSION_LATEST}"
goenv global "${GO_VERSION_LATEST}"
goenv versions
echo "$("${GOROOT}/bin/go" version) installed"

################################################################################
# Node
################################################################################
export NVM_DIR="${HOME}/.nvm"
# shellcheck disable=SC1091
. "/opt/homebrew/opt/nvm/nvm.sh"
nvm install --lts
npm install -g yarn

################################################################################
# IntelliJ
################################################################################
mkdir -p ~/Library/LaunchAgents
cat <<'EOF' >~/Library/LaunchAgents/me.graham.goenv.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>me.graham.goenv</string>
  <key>ProgramArguments</key>
  <array>
    <string>sh</string>
    <string>-c</string>
    <string>launchctl setenv GOPATH /Users/graham/.go &amp;&amp; launchctl setenv GOBIN /Users/graham/.go/bin</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/me.graham.goenv.plist 2>/dev/null
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/me.graham.goenv.plist
