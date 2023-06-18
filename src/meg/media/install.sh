#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media/audio
if [ $(grep "/data/media/audio" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Audio]
  comment = Media Files
  path = /data/media/audio
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
mkdir -vp /data/media/movies
if [ $(grep "/data/media/movies" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Movies]
  comment = Media Files
  path = /data/media/movies
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
mkdir -vp /data/media/series
if [ $(grep "/data/media/series" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Series]
  comment = Media Files
  path = /data/media/series
  browseable = yes
  read only = no
  guest ok = yes

EOF
fi
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
