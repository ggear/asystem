unifi-os shell
curl -L https://raw.githubusercontent.com/boostchicken/udm-utilities/master/on-boot-script/packages/udm-boot_1.0.1-1_all.deb -o udm-boot_1.0.1-1_all.deb
dpkg -i udm-boot_1.0.1-1_all.deb
exit

vi /mnt/data/on_boot.d/keys.sh
#!/bin/sh
mkdir -p /home
adduser -D graham
mkdir -p /home/graham/.ssh
cat <<EOF >> /home/graham/.ssh/authorized_keys
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC17bbhX9GtT/YyDrYO98Q9xzfyhn3WtBbftpFJ1yTm0wkssNMrW6YNjW2dVDm2qPgJUg9pKqw+XdyDUcxKWal1mLecPDYNAJgU0mJkFehDAxW91YNzjCH+kY70mVgZCzhi6XAx8pX5TDDHRMNnp76OyblMlge8g21tf3AwrzvJIQuC7UTrJYRWsxAIxTQBKqPW96JfvPLXk9l+vs31xC1y+wbWlKRey8LpYi4v/dePkkpQaac4R2DR4AlJNPRsoSn+W1zYYMi34bw4smpglrH83fA42rWClPkth/X2RzXPrQMyBNPFLalMbDe+xXMq6ExdfTlU6gE4s8dW4Gi3b1J1 graham.gear@gmail.com
EOF
chown -R graham.users /home/graham
chmod 711 /home
chmod 700 /home/graham
chmod 700 /home/graham/.ssh
chmod 600 /home/graham/.ssh/authorized_keys
