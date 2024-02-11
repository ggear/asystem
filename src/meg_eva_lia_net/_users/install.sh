#!/bin/sh

user_add() {
  if [ -d "${3}" ]; then
    if [ ${4} ]; then
      [ $(grep "${1}" "/etc/passwd" | wc -l) -eq 0 ] && adduser -D "${1}" 2>/dev/null
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
      chown ${1} "${3}${1}" 2>/dev/null || true
      chgrp ${2} "${3}${1}" 2>/dev/null || true
      chown -R ${1} "${3}${1}/.ssh" 2>/dev/null || true
      chgrp -R ${2} "${3}${1}/.ssh" 2>/dev/null || true
    fi
  fi
}

user_add 'root' 'root' '/' false
user_add 'root' 'root' '/var/' false
user_add 'graham' 'users' '/home/' true
user_add 'graham' 'staff' '/Users/' true

mkdir -p /home/asystem
[ ! -L ${HOME}/home ] && ln -s /home/asystem ${HOME}/home || true

mkdir -p /var/lib/asystem/install
[ ! -L ${HOME}/install ] && ln -s /var/lib/asystem/install ${HOME}/install || true
