#!/bin/sh

key_append() {
  if [ ! -e "${3}/${1}/.ssh/authorized_keys" ] || [ $(grep graham "${3}/${1}/.ssh/authorized_keys" | wc -l) -eq 0 ]; then
    [ -d "${3}" ] && mkdir -p ${3}
    [ $(grep "${1}" "/etc/passwd" | wc -l) -eq 0 ] && adduser -D "${1}"
    mkdir -p ${3}/${1}/.ssh
    cat <<EOF >>${3}/${1}/.ssh/authorized_keys
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC17bbhX9GtT/YyDrYO98Q9xzfyhn3WtBbftpFJ1yTm0wkssNMrW6YNjW2dVDm2qPgJUg9pKqw+XdyDUcxKWal1mLecPDYNAJgU0mJkFehDAxW91YNzjCH+kY70mVgZCzhi6XAx8pX5TDDHRMNnp76OyblMlge8g21tf3AwrzvJIQuC7UTrJYRWsxAIxTQBKqPW96JfvPLXk9l+vs31xC1y+wbWlKRey8LpYi4v/dePkkpQaac4R2DR4AlJNPRsoSn+W1zYYMi34bw4smpglrH83fA42rWClPkth/X2RzXPrQMyBNPFLalMbDe+xXMq6ExdfTlU6gE4s8dW4Gi3b1J1 graham.gear@gmail.com
EOF
    chown -R ${1}.${2} ${3}/${1}
    [ -d "${3}" ] && chmod 711 ${3}
    chmod 700 ${3}/${1}
    chmod 700 ${3}/${1}/.ssh
    chmod 600 ${3}/${1}/.ssh/authorized_keys
  fi
}

key_append 'root' 'root' ''
key_append 'graham' 'users' '/home'

[ ! -L /root/home ] && ln -s /home/asystem /root/home
[ ! -L /var/lib/asystem/install/$(hostname) ] && ln -s /var/lib/asystem/install/$(hostname) install
