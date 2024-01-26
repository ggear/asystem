#!/bin/bash

################################################################################
# Samba
################################################################################
for INDEX in {1..3}; do
  mkdir -vp /data/media/${INDEX}
  if [ $(grep "/data/media/${INDEX}" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
    cat <<EOF >>/etc/samba/smb.conf
[Media ${INDEX}]
  comment = Media Files
  path = /data/media/${INDEX}
  browseable = yes
  read only = no
  guest ok = yes

EOF
  fi
done
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
