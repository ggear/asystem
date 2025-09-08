#!/bin/bash

################################################################################
# Samba
################################################################################
cat <<EOF >/etc/samba/smb.conf
[global]
  server min protocol = SMB2
  server max protocol = SMB3
  client min protocol = SMB2
  client max protocol = SMB3
  server role = standalone server
  workgroup = WORKGROUP
  log file = /var/log/samba/log.%m
  logging = file
  max log size = 1000
  load printers = no
  access based share enum = no
  hide unreadable = no
  panic action = /usr/share/samba/panic-action %d
  obey pam restrictions = yes
  unix password sync = yes
  passwd program = /usr/bin/passwd %u
  passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
  pam password change = yes
  map to guest = bad user
  usershare allow guests = yes
  mdns name = mdns

  # macOS
  veto files = /.DS_Store/.TemporaryItems/.Trashes/
  delete veto files = yes
  vfs objects = catia fruit streams_xattr
  fruit:metadata = stream
  fruit:resource = file
  fruit:encoding = native
  fruit:posix_rename = yes
  fruit:veto_appledouble = no
  fruit:delete_empty_adfiles = no
  fruit:wipe_intentionally_left_blank_rfork = yes
  fruit:zero_file_id = yes
  fruit:copyfile = yes
  fruit:model = MacSamba
  #fruit:model = TimeCapsule9,119

  # Performance
  sync always = yes
  strict sync = no
  strict locking = yes
  strict allocate = yes
  oplocks = no
  level2 oplocks = no
  kernel oplocks = no
  use sendfile = yes
  min receivefile size = 16384
  write cache size = 262144
  aio read size = 1M
  aio write size = 1M
  aio max threads = 100

  # Optional: reduce caching for directory listings
  max xmit = 65535
  deadtime = 15

  # Encoding
  unix charset = UTF-8
  dos charset = CP437

  # Linux-friendly
  map archive = no
  map hidden = no
  map readonly = no
  map system = no

EOF
for SHARE_DIR in $(grep -v '^#' /etc/fstab | grep '/share' | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  SHARE_INDEX=$(echo ${SHARE_DIR} | awk 'BEGIN{FS=OFS="/"}{print $3}')
  rm -rf ${SHARE_DIR}/lost+found
  mkdir -p ${SHARE_DIR}/backup/data
  mkdir -p ${SHARE_DIR}/backup/media
  mkdir -p ${SHARE_DIR}/backup/service
  mkdir -p ${SHARE_DIR}/backup/timemachine
  mkdir -p ${SHARE_DIR}/data
  mkdir -p ${SHARE_DIR}/media
  mkdir -p ${SHARE_DIR}/service
  mkdir -p ${SHARE_DIR}/service/mlflow
  mkdir -p ${SHARE_DIR}/tmp
  chown -R graham:users ${SHARE_DIR}
  cat <<EOF >>/etc/samba/smb.conf
[share-${SHARE_INDEX}]
  comment = Share-${SHARE_INDEX} Files
  path = ${SHARE_DIR}
  public = yes
  browseable = yes
  read only = no
  writeable = yes
  force user = graham
  force group = users
  create mask = 0666
  directory mask = 0777
  force create mode = 0666
  force directory mode = 0777

EOF

  # TODO: Disable Time Machine share until we want it again
  #  cat <<EOF >>/etc/samba/smb.conf
  #[time-machine-${SHARE_INDEX}]
  #  comment = Time-Machine-${SHARE_INDEX} Files
  #  path = ${SHARE_DIR}/backup/timemachine
  #  public = yes
  #  browseable = yes
  #  read only = no
  #  writeable = yes
  #  force user = graham
  #  force group = users
  #  create mask = 0640
  #  directory mask = 0750
  #  force create mode = 0640
  #  force directory mode = 0750
  #  fruit:aapl = yes
  #  fruit:time machine = yes
  #  fruit:time machine max size = "4 T"
  #  vfs objects = fruit streams_xattr
  #
  #EOF

done

for _smb in smb.service smbd.service nmb.service nmbd.service remote-fs.target; do
  systemctl list-unit-files ${_smb} | grep -q ${_smb} && systemctl enable ${_smb} && systemctl restart ${_smb} && systemctl --no-pager status ${_smb}
done

[ -d /share ] && ls -d /share/* >/dev/null 2>&1 && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage /share/*
