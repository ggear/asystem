#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

#   volumes.sh [check|apply|format] [--force] [--disk=/dev/sdX] [--serial=SERIAL]
#
#   check   read only, resolves every declared volume and reports drift
#   apply   converges /etc/fstab, mountpoints and mounts, what install.sh runs
#   format  prepares a blank disk as the btrfs backup volume, the only destructive verb
#
# Every verb is idempotent. format refuses unless all of these hold:
#
#   1. The repo fstab declares that volume btrfs
#   2. The declared PARTLABEL resolves nowhere, so a prepared disk is never touched twice
#   3. The param 'disk' names a whole disk and the param 'serial' matches it, since /dev/sdX moves between boots
#   4. Nothing on it is mounted, swap or held by device-mapper, and no fstab entry resolves to it
#   5. The disk is blank with no partition, label, filesystem or signature of any kind
#   6. The param 'force' is given, otherwise the plan is printed and nothing changes

set -uo pipefail

VOLUMES_ACTION="apply"
VOLUMES_FORCE="${VOLUMES_FORCE:-false}"
VOLUMES_DISK=""
VOLUMES_SERIAL=""
VOLUMES_FAULTS=0
VOLUMES_CHANGED=0

while [ "$#" -gt 0 ]; do
  case "$1" in
  check | apply | format) VOLUMES_ACTION="$1" ;;
  --force) VOLUMES_FORCE="true" ;;
  --disk=*) VOLUMES_DISK="${1#--disk=}" ;;
  --disk)
    shift
    VOLUMES_DISK="${1:-}"
    ;;
  --serial=*) VOLUMES_SERIAL="${1#--serial=}" ;;
  --serial)
    shift
    VOLUMES_SERIAL="${1:-}"
    ;;
  *)
    echo "Usage: ${0} [check|apply|format] [--force] [--disk=/dev/sdX] [--serial=SERIAL]" >&2
    exit 2
    ;;
  esac
  shift
done

VOLUMES_SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fstab"
VOLUMES_SUBVOLUME_OPTS="noatime,compress=zstd:3"

volumes_fault() {
  echo "❌ $*" >&2
  VOLUMES_FAULTS=$((VOLUMES_FAULTS + 1))
}

volumes_report() { echo "   $*"; }

volumes_changed() {
  echo "   $*"
  VOLUMES_CHANGED=$((VOLUMES_CHANGED + 1))
}

volumes_forced() {
  [ "${VOLUMES_FORCE}" = "true" ] && return 0
  volumes_fault "refusing to $* without [--force]"
  return 1
}

volumes_entries() {
  awk '$1 !~ /^#/ && NF >= 4 && ($2 == "/share" || $2 ~ /^\/share\// || $2 == "/backup" || $2 ~ /^\/backup\//) {
    print $2 "\t" $1 "\t" $3 "\t" $4
  }' "${1}"
}

volumes_noauto() {
  case ",${1}," in *,noauto,*) return 0 ;; *) return 1 ;; esac
}

volumes_device() {
  case "${1}" in
  PARTLABEL=*) echo "/dev/disk/by-partlabel/${1#PARTLABEL=}" ;;
  PARTUUID=*) echo "/dev/disk/by-partuuid/${1#PARTUUID=}" ;;
  UUID=*) echo "/dev/disk/by-uuid/${1#UUID=}" ;;
  LABEL=*) echo "/dev/disk/by-label/${1#LABEL=}" ;;
  /dev/*) echo "${1}" ;;
  *) echo "" ;;
  esac
}

volumes_mounted() {
  findmnt -rn -o TARGET | awk '$1 == "/share" || $1 ~ /^\/share\// || $1 == "/backup" || $1 ~ /^\/backup\//' | sort
}

volumes_local_shares() {
  findmnt -rn -o TARGET,SOURCE,FSTYPE 2>/dev/null | while read -r target source fstype; do
    [[ "${target}" =~ ^/share/[0-9]+$ ]] || continue
    case "${fstype}" in ext4 | xfs | btrfs | f2fs) ;; *) continue ;; esac
    case "${source}" in /dev/*) ;; *) continue ;; esac
    printf '%s\n' "${target}"
  done | sort -u
}

volumes_unmount() {
  local target="$1"
  mountpoint -q "${target}" || return 0
  sync
  umount "${target}" 2>/dev/null || umount -l "${target}" 2>/dev/null
  mountpoint -q "${target}" && return 1
  return 0
}

volumes_holders() {
  local node holders
  node="$(basename "$(readlink -f "${1}")")"
  holders="$(find "/sys/class/block/${node}" -mindepth 2 -maxdepth 2 -path '*/holders/*' -printf '%f\n' 2>/dev/null)"
  printf '%s' "${holders}"
}

volumes_disk_guard() {
  local disk="$1" label="$2" node serial kind used fstypes partlabels spec resolved held
  node="$(basename "$(readlink -f "${disk}")")"
  kind="$(lsblk -drno TYPE "${disk}" 2>/dev/null)"
  if [ "${kind}" != "disk" ]; then
    volumes_fault "[${disk}] is a [${kind:-unknown}], --disk must name a whole disk, never a partition"
    return 1
  fi
  serial="$(lsblk -drno SERIAL "${disk}" 2>/dev/null)"
  if [ -z "${VOLUMES_SERIAL}" ]; then
    volumes_fault "[--serial] is required to format, [${disk}] reports serial [${serial:-none}], pass it back to confirm the disk"
    return 1
  fi
  if [ "${VOLUMES_SERIAL}" != "${serial}" ]; then
    volumes_fault "[${disk}] reports serial [${serial:-none}] but [--serial] said [${VOLUMES_SERIAL}], refusing, a device name can move between boots"
    return 1
  fi
  used="$(lsblk -rno MOUNTPOINT "${disk}" 2>/dev/null | grep -c .)"
  if [ "${used}" -ne 0 ]; then
    volumes_fault "[${disk}] has [${used}] mounted partition(s), refusing to touch it"
    return 1
  fi
  if swapon --show=NAME --noheadings 2>/dev/null | grep -q "^/dev/${node}"; then
    volumes_fault "[${disk}] is in use as swap, refusing"
    return 1
  fi
  held="$(volumes_holders "${disk}")"
  if [ -n "${held}" ]; then
    volumes_fault "[${disk}] has device-mapper or raid holders [$(printf '%s' "${held}" | tr '\n' ' ')], refusing"
    return 1
  fi
  fstypes="$(lsblk -rno FSTYPE "${disk}" 2>/dev/null | sort -u | grep -c -E '^(LVM2_member|linux_raid_member|crypto_LUKS)$')"
  if [ "${fstypes}" -ne 0 ]; then
    volumes_fault "[${disk}] carries an LVM, mdraid or LUKS member, refusing"
    return 1
  fi
  partlabels="$(lsblk -rno PARTLABEL "${disk}" 2>/dev/null | grep . | tr '\n' ' ')"
  if printf '%s' "${partlabels}" | grep -q '\bshare_'; then
    volumes_fault "[${disk}] carries a [share_*] partition [${partlabels}], refusing to format a share disk"
    return 1
  fi
  if printf '%s' "${partlabels}" | grep -q '\bbackup_'; then
    volumes_fault "[${disk}] already carries a backup partition [${partlabels}], refusing, it belongs to a host that declares that label"
    return 1
  fi
  if printf '%s' "${partlabels}" | grep -qiE 'efi|boot|recovery|ibootsystem'; then
    volumes_fault "[${disk}] carries a system partition [${partlabels}], refusing"
    return 1
  fi
  while read -r spec; do
    [ -n "${spec}" ] || continue
    resolved="$(volumes_device "${spec}")"
    [ -n "${resolved}" ] && [ -e "${resolved}" ] || continue
    case "$(readlink -f "${resolved}")" in
    /dev/"${node}" | /dev/"${node}"[0-9]* | /dev/"${node}"p[0-9]*)
      volumes_fault "[${disk}] is already claimed by [/etc/fstab] entry [${spec}], refusing"
      return 1
      ;;
    esac
  done < <(awk '$1 !~ /^#/ && NF >= 2 { print $1 }' /etc/fstab 2>/dev/null)
  if [ -e "/dev/disk/by-partlabel/${label}" ]; then
    volumes_fault "[${label}] appeared under [/dev/disk/by-partlabel] while checking, refusing"
    return 1
  fi
  volumes_disk_clean "${disk}" || return 1
  return 0
}

volumes_disk_clean() {
  local disk="$1" partitions partlabels fstypes signatures
  partitions="$(lsblk -rno NAME "${disk}" 2>/dev/null | tail -n +2 | tr '\n' ' ')"
  partlabels="$(lsblk -rno PARTLABEL "${disk}" 2>/dev/null | grep . | tr '\n' ' ')"
  fstypes="$(lsblk -rno FSTYPE "${disk}" 2>/dev/null | grep . | sort -u | tr '\n' ' ')"
  signatures="$(wipefs -n "${disk}" 2>/dev/null | tail -n +2 | awk '{print $3}' | sort -u | tr '\n' ' ')"
  if [ -z "${partitions}" ] && [ -z "${partlabels}" ] && [ -z "${fstypes}" ] && [ -z "${signatures}" ]; then
    volumes_report "[${disk}] is clean, no partition, label, filesystem or signature"
    return 0
  fi
  volumes_fault "[${disk}] is not clean, it carries partition(s) [${partitions:-none}] label(s) [${partlabels:-none}] filesystem(s) [${fstypes:-none}] signature(s) [${signatures:-none}]"
  volumes_report "a format only ever writes to a blank disk, so nothing that already belongs to something can be overwritten"
  volumes_report "if this disk really is spare, clear it deliberately by hand and run the format again"
  volumes_report "wipefs -a ${disk} && sgdisk -Z ${disk} && partprobe ${disk}"
  return 1
}

volumes_inspect() {
  local target source fstype opts device present held actual
  echo && echo "-- declared volumes"
  while IFS=$'\t' read -r target source fstype opts; do
    [ -n "${target}" ] || continue
    device="$(volumes_device "${source}")"
    present="no"
    [ -n "${device}" ] && [ -e "${device}" ] && present="yes"
    held="$(findmnt -rn -o SOURCE --target "${target}" 2>/dev/null)"
    mountpoint -q "${target}" || held=""
    if [ -z "${device}" ]; then
      volumes_report "[${target}] remote [${source}] mounted [$([ -n "${held}" ] && echo yes || echo no)]"
      continue
    fi
    volumes_report "[${target}] device [${source}] present [${present}] mounted [$([ -n "${held}" ] && echo yes || echo no)] declared [${fstype}]"
    if [ "${present}" = "no" ]; then
      volumes_noauto "${opts}" ||
        volumes_report "[${target}] device is absent, expected only while its disk is powered down"
      continue
    fi
    actual="$(blkid -s TYPE -o value "$(readlink -f "${device}")" 2>/dev/null)"
    if [ -n "${actual}" ] && [ "${actual}" != "${fstype}" ]; then
      volumes_fault "[${target}] declares [${fstype}] but [${device}] holds [${actual}]"
    fi
    if [ -n "${held}" ] && [ "$(readlink -f "${held}")" != "$(readlink -f "${device}")" ]; then
      volumes_fault "[${target}] is mounted from [${held}] but declares [${device}]"
    fi
  done < <(volumes_entries "${VOLUMES_SOURCE}")
  local seen duplicate
  seen="$(while IFS=$'\t' read -r target source _ _; do
    [ -n "${target}" ] || continue
    device="$(volumes_device "${source}")"
    [ -n "${device}" ] && [ -e "${device}" ] && readlink -f "${device}"
  done < <(volumes_entries "${VOLUMES_SOURCE}"))"
  duplicate="$(printf '%s\n' "${seen}" | sort | uniq -d)"
  if [ -n "${duplicate}" ]; then
    while read -r device; do
      [ -n "${device}" ] || continue
      volumes_fault "[${device}] is claimed by more than one declared volume"
    done <<<"${duplicate}"
  fi
}

volumes_backup_target() {
  awk '$1 !~ /^#/ && NF >= 4 && ($2 == "/backup" || $2 ~ /^\/backup\//) { print $2 "\t" $1 "\t" $3 "\t" $4; exit }' "${VOLUMES_SOURCE}"
}

volumes_subvolumes() {
  local mount="$1" share name
  btrfs subvolume show "${mount}/share" >/dev/null 2>&1 ||
    { btrfs subvolume create "${mount}/share" >/dev/null && volumes_changed "created subvolume [${mount}/share]"; }
  while read -r share; do
    [ -n "${share}" ] || continue
    name="$(basename "${share}")"
    btrfs subvolume show "${mount}/share/${name}" >/dev/null 2>&1 && continue
    btrfs subvolume create "${mount}/share/${name}" >/dev/null &&
      volumes_changed "created subvolume [${mount}/share/${name}]"
  done < <(volumes_local_shares)
}

volumes_check() {
  volumes_inspect
  local target source fstype opts device label
  IFS=$'\t' read -r target source fstype opts < <(volumes_backup_target)
  if [ -z "${target:-}" ]; then
    echo && volumes_report "no backup volume declared for this host"
    return 0
  fi
  echo && echo "-- backup volume"
  device="$(volumes_device "${source}")"
  label="${source#PARTLABEL=}"
  if [ -z "${device}" ] || [ ! -e "${device}" ]; then
    volumes_report "[${target}] label [${label}] is not present, run [volumes.sh format --disk=/dev/sdX --force] with the disk powered on"
    return 0
  fi
  local actual
  actual="$(blkid -s TYPE -o value "$(readlink -f "${device}")" 2>/dev/null)"
  volumes_report "[${target}] label [${label}] resolves to [$(readlink -f "${device}")] holding [${actual:-none}]"
  if [ "${actual}" != "btrfs" ]; then
    volumes_report "[${target}] is not btrfs, so snapshots stay inert, formatting would destroy [${actual:-an unformatted disk}]"
    return 0
  fi
  if mountpoint -q "${target}"; then
    btrfs subvolume show "${target}/share" >/dev/null 2>&1 ||
      volumes_fault "[${target}/share] is not a subvolume, so nothing under it can be snapshotted"
    local share name
    while read -r share; do
      [ -n "${share}" ] || continue
      name="$(basename "${share}")"
      btrfs subvolume show "${target}/share/${name}" >/dev/null 2>&1 ||
        volumes_fault "[${target}/share/${name}] is not a subvolume, so share [${share}] is never snapshotted"
    done < <(volumes_local_shares)
  else
    volumes_report "[${target}] is not mounted, subvolume layout not checked"
  fi
}

volumes_apply() {
  local stale
  if [ -f /etc/fstab ] && diff -q "${VOLUMES_SOURCE}" /etc/fstab >/dev/null 2>&1; then
    volumes_report "[/etc/fstab] already matches the declaration"
  else
    [ ! -f /etc/fstab.bak ] && cp -v /etc/fstab /etc/fstab.bak
    cp -f /etc/fstab "/etc/fstab.$(date +%Y-%m-%d_%H-%M-%S).bak"
    diff -uw /etc/fstab "${VOLUMES_SOURCE}"
    cp -f "${VOLUMES_SOURCE}" /etc/fstab
    volumes_changed "wrote [/etc/fstab] from the declaration"
  fi

  local target source fstype opts
  while IFS=$'\t' read -r target source fstype opts; do
    [ -n "${target}" ] || continue
    [ -d "${target}" ] || volumes_changed "created mountpoint [${target}]"
    mkdir -p "${target}" && chmod 750 "${target}" && chown graham:users "${target}"
  done < <(volumes_entries "${VOLUMES_SOURCE}")

  stale="$(comm -23 <(volumes_mounted) <(volumes_entries "${VOLUMES_SOURCE}" | cut -f1 | sort) | sort -r)"
  if [ -n "${stale}" ]; then
    while read -r target; do
      [ -n "${target}" ] || continue
      volumes_forced "unmount [${target}], which is mounted but no longer declared" || continue
      if volumes_unmount "${target}"; then
        volumes_changed "unmounted undeclared [${target}]"
      else
        volumes_fault "could not unmount [${target}]"
      fi
    done <<<"${stale}"
  fi

  for _smb in smb.service smbd.service; do
    systemctl list-unit-files ${_smb} 2>/dev/null | grep -q ${_smb} &&
      ! systemctl list-unit-files ${_smb} | grep -q masked &&
      ! systemctl is-active --quiet ${_smb} && systemctl start ${_smb}
  done

  while IFS=$'\t' read -r target source fstype opts; do
    [ -n "${target}" ] || continue
    volumes_noauto "${opts}" && continue
    mountpoint -q "${target}" && continue
    if mount "${target}" 2>/tmp/volumes_errors.log; then
      volumes_changed "mounted [${target}]"
    else
      volumes_report "[${target}] did not mount, expected for an automount or a nofail entry"
      cat /tmp/volumes_errors.log
    fi
  done < <(volumes_entries "${VOLUMES_SOURCE}")

  find /share -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null
  find /backup -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null
  while IFS=$'\t' read -r target source fstype opts; do
    [ -n "${target}" ] || continue
    mkdir -p "${target}" && chmod 750 "${target}" && chown graham:users "${target}"
  done < <(volumes_entries "${VOLUMES_SOURCE}")

  systemctl daemon-reload
  local unit
  for unit in $(systemctl list-units --type=automount --no-legend | awk '/share-[0-9]+\.automount$/ {print $2}'); do
    systemctl stop "${unit}"
    systemctl disable "${unit}"
  done
  systemctl daemon-reload
  systemctl reset-failed
  [ "$(find /share -mindepth 1 -maxdepth 1 2>/dev/null)" ] &&
    duf -width 250 -style ascii -output mountpoint,size,used,avail,usage,filesystem /share/*
  volumes_check
}

volumes_format() {
  local target source fstype opts label device part tool
  IFS=$'\t' read -r target source fstype opts < <(volumes_backup_target)
  if [ -z "${target:-}" ]; then
    volumes_fault "no backup volume is declared for this host, nothing to format"
    return 1
  fi
  case "${source}" in
  PARTLABEL=*) label="${source#PARTLABEL=}" ;;
  *)
    volumes_fault "backup volume [${target}] is declared as [${source}], only a PARTLABEL can be prepared"
    return 1
    ;;
  esac
  if [ "${fstype}" != "btrfs" ]; then
    volumes_fault "backup volume [${target}] declares [${fstype}], change the repo fstab to [btrfs] with [${VOLUMES_SUBVOLUME_OPTS},noauto] and release before formatting"
    return 1
  fi
  for tool in sgdisk wipefs partprobe mkfs.btrfs btrfs; do
    command -v "${tool}" >/dev/null 2>&1 && continue
    volumes_fault "[${tool}] is not installed, needed to prepare a backup disk, install [gdisk] and [btrfs-progs]"
  done
  [ "${VOLUMES_FAULTS}" -eq 0 ] || return 1

  device="/dev/disk/by-partlabel/${label}"
  if [ -e "${device}" ]; then
    part="$(readlink -f "${device}")"
    local actual
    actual="$(blkid -s TYPE -o value "${part}" 2>/dev/null)"
    if [ "${actual}" = "btrfs" ]; then
      volumes_report "[${label}] already present on [${part}] as btrfs, converging subvolumes only"
      local mounted="no"
      if ! mountpoint -q "${target}"; then
        mount -o "${VOLUMES_SUBVOLUME_OPTS}" "${part}" "${target}" || {
          volumes_fault "could not mount [${part}] on [${target}]"
          return 1
        }
        mounted="yes"
      fi
      volumes_subvolumes "${target}"
      btrfs subvolume list "${target}"
      [ "${mounted}" = "yes" ] && volumes_unmount "${target}"
      return 0
    fi
    volumes_fault "[${label}] already present on [${part}] holding [${actual:-no filesystem}], refusing to relabel or reformat a disk that already carries this label"
    return 1
  fi

  if [ -z "${VOLUMES_DISK}" ]; then
    volumes_fault "[${label}] is absent and no [--disk] was given, power the disk on and name it explicitly"
    lsblk -o NAME,SIZE,TYPE,PARTLABEL,FSTYPE,MOUNTPOINT,MODEL,SERIAL
    return 1
  fi
  if [ ! -b "${VOLUMES_DISK}" ]; then
    volumes_fault "[${VOLUMES_DISK}] is not a block device"
    return 1
  fi
  echo && echo "-- candidate disk" && lsblk -o NAME,SIZE,TYPE,PARTLABEL,FSTYPE,MOUNTPOINT,MODEL,SERIAL "${VOLUMES_DISK}"
  volumes_disk_guard "${VOLUMES_DISK}" "${label}" || return 1
  echo && echo "-- plan"
  volumes_report "create one GPT partition spanning the blank disk [${VOLUMES_DISK}] named [${label}]"
  volumes_report "make btrfs labelled [${label}] on it, [xxhash] checksums and [dup] metadata"
  volumes_report "create subvolume [share] and one per locally owned share"
  volumes_forced "partition and format the blank disk [${VOLUMES_DISK}] as [${label}]" || return 1

  sgdisk -Z "${VOLUMES_DISK}" >/dev/null || { volumes_fault "could not clear the partition table on [${VOLUMES_DISK}]"; return 1; }
  sgdisk -n 1:0:0 -t 1:8300 -c 1:"${label}" "${VOLUMES_DISK}" >/dev/null ||
    { volumes_fault "could not partition [${VOLUMES_DISK}]"; return 1; }
  partprobe "${VOLUMES_DISK}"
  udevadm settle 2>/dev/null
  if [ ! -e "${device}" ]; then
    volumes_fault "[${label}] did not appear under [/dev/disk/by-partlabel] after partitioning"
    return 1
  fi
  part="$(readlink -f "${device}")"
  volumes_changed "partitioned [${VOLUMES_DISK}] as [${label}] on [${part}]"
  mkfs.btrfs -L "${label}" --csum xxhash -m dup -f "${part}" >/dev/null ||
    { volumes_fault "could not make btrfs on [${part}]"; return 1; }
  volumes_changed "made btrfs [${label}] on [${part}] with [xxhash] checksums and [dup] metadata"
  mount -o "${VOLUMES_SUBVOLUME_OPTS}" "${part}" "${target}" || {
    volumes_fault "could not mount [${part}] on [${target}]"
    return 1
  }
  volumes_subvolumes "${target}"
  btrfs subvolume list "${target}"
  volumes_unmount "${target}" || volumes_fault "could not unmount [${target}]"
}

echo && echo "Volumes ${VOLUMES_ACTION} against [$(hostname)] forced [${VOLUMES_FORCE}]"
if [ ! -f "${VOLUMES_SOURCE}" ]; then
  echo && echo "❌ Could not find fstab file [${VOLUMES_SOURCE}]" && echo
  exit 1
fi
case "${VOLUMES_ACTION}" in
check) volumes_check ;;
apply) volumes_apply ;;
format) volumes_format ;;
esac
echo
if [ "${VOLUMES_FAULTS}" -ne 0 ]; then
  echo "❌ Volumes ${VOLUMES_ACTION} found [${VOLUMES_FAULTS}] fault(s), changed [${VOLUMES_CHANGED}]" && echo
  exit 1
fi
echo "✅ Volumes ${VOLUMES_ACTION} converged, changed [${VOLUMES_CHANGED}]" && echo