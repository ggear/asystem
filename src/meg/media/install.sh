#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media/Audio
if [ $(grep "/data/media/Audio" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Audio]
  comment = Media Files
  path = /data/media/Audio
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
mkdir -vp /data/media/Movies
if [ $(grep "/data/media/Movies" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Movies]
  comment = Media Files
  path = /data/media/Movies
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
mkdir -vp /data/media/Series
if [ $(grep "/data/media/Series" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Series]
  comment = Media Files
  path = /data/media/Series
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
