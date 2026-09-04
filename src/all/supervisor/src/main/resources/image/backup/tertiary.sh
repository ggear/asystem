# shellcheck shell=bash

BACKUP_DISK_SECONDS="${BACKUP_DISK_SECONDS:-120}"

backup_ready() {
  local source fstype
  read -r fstype source < <(findmnt -M /backup -n -o FSTYPE,SOURCE 2>/dev/null) || return 1
  case "${fstype}" in ext4 | xfs | btrfs | f2fs) ;; *) return 1 ;; esac
  case "${source}" in /dev/*) return 0 ;; *) return 1 ;; esac
}

stage_start() {
  local share index target failed=0 fstab_target fstab_type
  if ! backup_attach; then
    echo "[tertiary] backup disk did not come up" >&2
    return 1
  fi
  if ! backup_ready; then
    echo "[tertiary] /backup is not a mounted local filesystem, refusing to mirror" >&2
    return 1
  fi
  while read -r fstab_target fstab_type; do
    case "${fstab_type}" in ext4 | xfs | btrfs | f2fs) ;; *) continue ;; esac
    backup_mount "${fstab_target}" || echo "[tertiary] could not mount [${fstab_target}]" >&2
  done < <(awk '$1 !~ /^#/ && $2 ~ /^\/share\/[0-9]+$/ { print $2, $3 }' /etc/fstab)
  while read -r share; do
    index="${share#/share/}"
    [[ "${index}" =~ ^[0-9]+$ ]] || continue
    target="/backup/share/${index}"
    mountpoint -q "${share}" || { echo "[tertiary] [${share}] vanished mid-run, skipping" >&2; failed=1; continue; }
    mountpoint -q /backup || { echo "[tertiary] /backup vanished mid-run, aborting" >&2; failed=1; break; }
    mkdir -p "${target}/.rsync"
    find "${target}/.rsync" -mindepth 1 -delete 2>/dev/null
    echo "[tertiary] mirroring [${share}] to [${target}]"
    local output
    output="$(rsync -a --delete --stats --exclude '/tmp/' --exclude '/.rsync/' \
      --temp-dir="${target}/.rsync" -- "${share}/" "${target}/" 2>&1)" || failed=1
    printf '%s\n' "${output}"
    backup_count "${output}"
  done < <(findmnt -rn -o TARGET,SOURCE,FSTYPE 2>/dev/null | while read -r mount source fstype; do
    [[ "${mount}" =~ ^/share/[0-9]+$ ]] || continue
    case "${fstype}" in ext4 | xfs | btrfs | f2fs) ;; *) continue ;; esac
    case "${source}" in /dev/*) printf '%s\n' "${mount}" ;; esac
  done | sort -u)
  if mountpoint -q /backup; then
    if command -v btrfs >/dev/null 2>&1 && backup_ready; then
      local subvolume name snapshots="/backup/.snapshots"
      for subvolume in /backup/share/*; do
        [ -d "${subvolume}" ] || continue
        btrfs subvolume show "${subvolume}" >/dev/null 2>&1 || continue
        name="$(basename "${subvolume}")"
        mkdir -p "${snapshots}/share/${name}"
        btrfs subvolume snapshot -r "${subvolume}" "${snapshots}/share/${name}/${BACKUP_RUN_ID}" >/dev/null 2>&1 &&
          echo "[tertiary] snapshot ${snapshots}/share/${name}/${BACKUP_RUN_ID}"
        backup_thin "${snapshots}/share/${name}"
      done
    fi
    backup_usage /backup
  fi
  stage_stop || true
  return "${failed}"
}

stage_stop() {
  pkill -TERM -f "rsync .*/backup/share" 2>/dev/null || true
  sync
  backup_detach
}

backup_targets() {
  awk '$1 !~ /^#/ && ($2 == "/backup" || $2 ~ /^\/backup\//) { print $2 }' /etc/fstab
}

backup_attach() {
  local deadline=$(( $(date +%s) + BACKUP_DISK_SECONDS )) target device pending failed=0
  while :; do
    pending=0
    while read -r target; do
      device="$(awk -v mp="${target}" '$1 !~ /^#/ && $2 == mp { print $1 }' /etc/fstab)"
      case "${device}" in
      PARTLABEL=*) [ -e "/dev/disk/by-partlabel/${device#PARTLABEL=}" ] || pending=1 ;;
      PARTUUID=*) [ -e "/dev/disk/by-partuuid/${device#PARTUUID=}" ] || pending=1 ;;
      UUID=*) [ -e "/dev/disk/by-uuid/${device#UUID=}" ] || pending=1 ;;
      LABEL=*) [ -e "/dev/disk/by-label/${device#LABEL=}" ] || pending=1 ;;
      /dev/*) [ -b "${device}" ] || pending=1 ;;
      *) : ;;
      esac
    done < <(backup_targets)
    [ "${pending}" -eq 0 ] && break
    if [ "$(date +%s)" -ge "${deadline}" ]; then
      echo "[tertiary] timed out after [${BACKUP_DISK_SECONDS}]s waiting for the backup disk to enumerate" >&2
      return 1
    fi
    sleep 2
  done
  while read -r target; do
    backup_mount "${target}" || failed=1
  done < <(backup_targets)
  return "${failed}"
}

backup_detach() {
  local target
  while read -r target; do
    mountpoint -q "${target}" || continue
    sync
    umount "${target}" || umount -l "${target}" || echo "[tertiary] could not unmount [${target}]" >&2
  done < <(backup_targets)
}
