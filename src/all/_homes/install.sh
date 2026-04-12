#!/usr/bin/env bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${SERVICE_INSTALL}" || exit 1

user_add() {
  local user_name="$1"
  local group_name="$2"
  local home_parent="$3"
  local should_create_user="$4"
  local home_path="${home_parent}${user_name}"
  local asystem_home="/home/asystem"

  if [ -d /Users ] || [ "${home_parent}" = "/Users/" ]; then
    asystem_home="/Users/asystem"
  fi
  mkdir -p "${asystem_home}"
  [ -d /root ] && [ ! -L /root/home ] && ln -s "${asystem_home}" /root/home || true
  mkdir -p /var/lib/asystem/install
  [ -d /root ] && [ ! -L /root/install ] && ln -s /var/lib/asystem/install /root/install || true

  if [ -d "${home_parent}" ]; then
    if [ "${should_create_user}" = "true" ]; then
      if ! grep -q "^${user_name}:" "/etc/passwd"; then
        adduser --disabled-password --shell /bin/bash --gecos "${user_name}" "${user_name}" 2>/dev/null || true
      fi
      if [ ! -d "${home_path}" ]; then
        mkdir -p "${home_path}" 2>/dev/null || true
        chmod 711 "${home_parent}" 2>/dev/null || true
      fi
    fi
    if [ -d "${home_path}" ]; then
      if [ ! -e "${home_path}/.ssh/authorized_keys" ] || ! grep -q "graham" "${home_path}/.ssh/authorized_keys"; then
        mkdir -p "${home_path}/.ssh"
        chmod 700 "${home_path}/.ssh"
        cat <<EOF >>"${home_path}/.ssh/authorized_keys"
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC17bbhX9GtT/YyDrYO98Q9xzfyhn3WtBbftpFJ1yTm0wkssNMrW6YNjW2dVDm2qPgJUg9pKqw+XdyDUcxKWal1mLecPDYNAJgU0mJkFehDAxW91YNzjCH+kY70mVgZCzhi6XAx8pX5TDDHRMNnp76OyblMlge8g21tf3AwrzvJIQuC7UTrJYRWsxAIxTQBKqPW96JfvPLXk9l+vs31xC1y+wbWlKRey8LpYi4v/dePkkpQaac4R2DR4AlJNPRsoSn+W1zYYMi34bw4smpglrH83fA42rWClPkth/X2RzXPrQMyBNPFLalMbDe+xXMq6ExdfTlU6gE4s8dW4Gi3b1J1 graham.gear@gmail.com
EOF
        chmod 600 "${home_path}/.ssh/authorized_keys"
      fi
      cat <<'EOF' >"${home_path}/.bashrc"
# .bashrc

export LANG=en_AU.UTF-8
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
      chown "${user_name}" "${home_path}" 2>/dev/null || true
      chgrp "${group_name}" "${home_path}" 2>/dev/null || true
      chown -R "${user_name}" "${home_path}/.ssh" 2>/dev/null || true
      chgrp -R "${group_name}" "${home_path}/.ssh" 2>/dev/null || true
    fi
  fi
}

key_copy() {
  local user_name="$1"
  local group_name="$2"
  local home_parent="$3"
  local home_path="${home_parent}${user_name}"
  local key_public="${SERVICE_INSTALL}/config/id_rsa.pub"
  local key_private="${SERVICE_INSTALL}/config/.id_rsa"

  if [ -d "${home_path}" ]; then
    mkdir -p "${home_path}/.ssh"
    if [ -f "${key_public}" ]; then
      cp -vf "${key_public}" "${home_path}/.ssh/id_rsa.pub"
    fi
    if [ -f "${key_private}" ]; then
      cp -vf "${key_private}" "${home_path}/.ssh/id_rsa"
      chmod 600 "${home_path}/.ssh/id_rsa" 2>/dev/null || true
    fi
    chown -R "${user_name}" "${home_path}/.ssh" 2>/dev/null || true
    chgrp -R "${group_name}" "${home_path}/.ssh" 2>/dev/null || true
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
