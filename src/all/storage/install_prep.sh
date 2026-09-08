#!/bin/bash

set -Eeuo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

if [[ "${SERVICE_FORM_FACTOR:-}" == "server" && "${SERVICE_COMMAND:-}" == "install" ]]; then

  SMB_CONF="/etc/samba/smb.conf"
  SMB_CONF_NEW="$(mktemp "${SMB_CONF}.XXXXXX")"
  SHARE_COUNT=0

  cleanup() {
    rm -f "${SMB_CONF_NEW}"
  }
  trap cleanup EXIT

  cat <<EOF >"${SMB_CONF_NEW}"
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
  unix charset = UTF-8
  dos charset = CP437
  sync always = yes
  strict sync = no
  strict locking = yes
  strict allocate = yes
  deadtime = 15
  oplocks = no
  level2 oplocks = no
  kernel oplocks = no
  use sendfile = yes
  min receivefile size = 16384
  max xmit = 65535
  aio read size = 1M
  aio write size = 1M
  aio max threads = 100
  map archive = no
  map hidden = no
  map readonly = no
  map system = no
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

EOF
  while IFS= read -r SHARE_DIR; do
    if [[ -z "${SHARE_DIR}" ]]; then
      echo "Skipping share with no mount point in [/etc/fstab]" >&2
      continue
    fi
    if ! mountpoint -q "${SHARE_DIR}"; then
      echo "Skipping share not mounted [${SHARE_DIR}]" >&2
      continue
    fi
    SHARE_INDEX=$(echo "${SHARE_DIR}" | awk 'BEGIN{FS=OFS="/"}{print $3}')
    rm -rf "${SHARE_DIR}/lost+found"
    mkdir -p "${SHARE_DIR}/backup"
    mkdir -p "${SHARE_DIR}/media"
    mkdir -p "${SHARE_DIR}/service"
    mkdir -p "${SHARE_DIR}/service/mlflow"
    mkdir -p "${SHARE_DIR}/tmp"
    chown graham:users \
      "${SHARE_DIR}" \
      "${SHARE_DIR}/backup" \
      "${SHARE_DIR}/media" \
      "${SHARE_DIR}/service" \
      "${SHARE_DIR}/service/mlflow" \
      "${SHARE_DIR}/tmp"
    SHARE_COUNT=$((SHARE_COUNT + 1))
    cat <<EOF >>"${SMB_CONF_NEW}"
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
    #  cat <<EOF >>"${SMB_CONF_NEW}"
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

  done < <(grep -v '^#' /etc/fstab | grep '/share' | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}')

  if [[ "${SHARE_COUNT}" -eq 0 ]]; then
    echo "Samba not reconfigured, no mounted shares found in [/etc/fstab]" >&2
  else
    chmod 644 "${SMB_CONF_NEW}"
    mv -f "${SMB_CONF_NEW}" "${SMB_CONF}"
    trap - EXIT

    for _smb in smb.service smbd.service nmb.service nmbd.service remote-fs.target; do
      if systemctl list-unit-files "${_smb}" | grep -q "${_smb}"; then
        systemctl enable "${_smb}" || echo "Failed to enable unit [${_smb}]" >&2
        systemctl restart "${_smb}" || echo "Failed to restart unit [${_smb}]" >&2
        systemctl --no-pager status "${_smb}" || true
      fi
    done
  fi

  { [ -d /share ] && ls -d /share/* >/dev/null 2>&1 && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage /share/*; } || true

fi
