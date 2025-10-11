#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

################################################################################
# Users setup
################################################################################
user_add() {
  if [ -d "${3}" ]; then
    if [ ${4} ]; then
      [ $(grep "${1}" "/etc/passwd" | wc -l) -eq 0 ] && adduser --disabled-password --shell /bin/bash --gecos "${1}" "${1}" 2>/dev/null
      [ -d "${3}${1}" ] && mkdir -p ${3}${1} && chmod 711 ${3} 2>/dev/null
    fi
    if [ -d "${3}${1}" ]; then
      if [ ! -e "${3}${1}/.ssh/authorized_keys" ] || [ $(grep graham "${3}${1}/.ssh/authorized_keys" | wc -l) -eq 0 ]; then
        mkdir -p ${3}${1}/.ssh
        chmod 700 ${3}${1}/.ssh
        cat <<EOF >>${3}${1}/.ssh/authorized_keys
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC17bbhX9GtT/YyDrYO98Q9xzfyhn3WtBbftpFJ1yTm0wkssNMrW6YNjW2dVDm2qPgJUg9pKqw+XdyDUcxKWal1mLecPDYNAJgU0mJkFehDAxW91YNzjCH+kY70mVgZCzhi6XAx8pX5TDDHRMNnp76OyblMlge8g21tf3AwrzvJIQuC7UTrJYRWsxAIxTQBKqPW96JfvPLXk9l+vs31xC1y+wbWlKRey8LpYi4v/dePkkpQaac4R2DR4AlJNPRsoSn+W1zYYMi34bw4smpglrH83fA42rWClPkth/X2RzXPrQMyBNPFLalMbDe+xXMq6ExdfTlU6gE4s8dW4Gi3b1J1 graham.gear@gmail.com
EOF
        chmod 600 ${3}${1}/.ssh/authorized_keys
      fi
      cat <<'EOF' >"${3}${1}/.bashrc"
# .bashrc

export LANG=en_AU.UTF-8
export LC_ALL=en_AU.UTF-8
export LC_COLLATE=C
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
export PS1="\[\e[95m\]\u@\h\[\e[0m\]:\w\$ "
export PROMPT_COMMAND='echo -ne "\033]0;${USER}@${HOSTNAME}: ${PWD}\007"'

bind '"\e[A": history-search-backward' 2>/dev/null
bind '"\e[B": history-search-forward' 2>/dev/null

alias dmesg='dmesg -T'
alias ls='ls ${LS_OPTIONS}'

PATH=/root/.pyenv/bin:${PATH}

EOF
      chown ${1} "${3}${1}" 2>/dev/null || true
      chgrp ${2} "${3}${1}" 2>/dev/null || true
      chown -R ${1} "${3}${1}/.ssh" 2>/dev/null || true
      chgrp -R ${2} "${3}${1}/.ssh" 2>/dev/null || true
    fi
  fi
}

key_copy() {
  if [ -d "${3}${1}" ]; then
    mkdir -p ${3}${1}/.ssh
    cp -rvf ${SERVICE_INSTALL}/config/id_rsa.pub ${3}${1}/.ssh
    cp -rvf ${SERVICE_INSTALL}/config/.id_rsa ${3}${1}/.ssh/id_rsa
    chown -R ${1} ${3}${1}/.ssh 2>/dev/null || true
    chgrp -R ${2} ${3}${1}/.ssh 2>/dev/null || true
  fi
}

user_add 'root' 'root' '/' false
user_add 'root' 'root' '/var/' false
user_add 'graham' 'users' '/home/' true
user_add 'graham' 'staff' '/Users/' true
key_copy 'root' 'root' '/'
key_copy 'root' 'root' '/var/'
key_copy 'graham' 'users' '/home/'
key_copy 'graham' 'staff' '/Users/'
