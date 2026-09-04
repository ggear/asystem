# shellcheck shell=bash

BACKUP_DISK_SECONDS="${BACKUP_DISK_SECONDS:-120}"
BACKUP_SCRUB_DAYS="${BACKUP_SCRUB_DAYS:-30}"
BACKUP_SCRUB_MARGIN="${BACKUP_SCRUB_MARGIN:-900}"
BACKUP_SCRUB_POLL="${BACKUP_SCRUB_POLL:-30}"

backup_ready() {
  local source fstype
  read -r fstype source < <(findmnt -M /backup -n -o FSTYPE,SOURCE 2>/dev/null) || return 1
  case "${fstype}" in ext4 | xfs | btrfs | f2fs) ;; *) return 1 ;; esac
  case "${source}" in /dev/*) return 0 ;; *) return 1 ;; esac
}

backup_scrub_counter() {
  local value
  value="$(printf '%s\n' "$1" | sed -n "s/^[[:space:]]*$2:[[:space:]]*//p" | head -1 | tr -dc '0-9')"
  printf '%s' "${value:-0}"
}

backup_scrub_document() {
  local state="$1" success="$2" started="$3" scrubbed="$4" progress="$5" found="$6" corrected="$7" uncorrectable="$8"
  mkdir -p "${BACKUP_STAGE_DIR}"
  cat >"${BACKUP_STAGE_DIR}/scrub.json.tmp" <<JSON
{
  "run_id": "${BACKUP_RUN_ID}",
  "state": "${state}",
  "started_ts": "$(date --iso-8601=seconds -d @"${started}")",
  "finished_ts": "$(date --iso-8601=seconds)",
  "duration_s": $(( $(date +%s) - started )),
  "success_bool": ${success},
  "scrubbed_mb": ${scrubbed},
  "progress_perc": ${progress},
  "errors_found": ${found},
  "errors_corrected": ${corrected},
  "errors_uncorrectable": ${uncorrectable}
}
JSON
  mv "${BACKUP_STAGE_DIR}/scrub.json.tmp" "${BACKUP_STAGE_DIR}/scrub.json"
  backup_publish "supervisor/${BACKUP_HOST}/backup/stage/tertiary/scrub/status" "$(cat "${BACKUP_STAGE_DIR}/scrub.json")"
}

backup_scrub_cancel() {
  command -v btrfs >/dev/null 2>&1 || return 0
  mountpoint -q /backup || return 0
  btrfs scrub cancel /backup >/dev/null 2>&1 || true
}

backup_scrub() {
  local status raw action started hard since state=finished success=true
  local scrubbed=0 progress=0 found=0 corrected=0 uncorrectable=0
  started="$(date +%s)"
  if ! command -v btrfs >/dev/null 2>&1; then
    echo "[tertiary] scrub skipped, no [btrfs] on the PATH" >&2
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  if ! btrfs filesystem show /backup >/dev/null 2>&1; then
    echo "[tertiary] scrub skipped, [/backup] is not btrfs"
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  status="$(btrfs scrub status /backup 2>/dev/null)"
  case "${status}" in
  *interrupted* | *aborted*) action="resume" ;;
  *)
    action="start"
    since="$(printf '%s\n' "${status}" | sed -n 's/^Scrub started:[[:space:]]*//p' | head -1)"
    if [ -n "${since}" ] &&
      [ "$(date -d "${since}" +%s 2>/dev/null || echo 0)" -gt "$(( started - BACKUP_SCRUB_DAYS * 86400 ))" ]; then
      echo "[tertiary] scrub skipped, the last pass started [${since}] within [${BACKUP_SCRUB_DAYS}] days"
      backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
      return 0
    fi
    ;;
  esac
  hard=0
  [ "${BACKUP_TIMEOUT_HOURS}" -gt 0 ] 2>/dev/null &&
    hard=$(( BACKUP_STARTED + BACKUP_TIMEOUT_HOURS * 3600 - BACKUP_SCRUB_MARGIN ))
  [ "${hard}" -gt 0 ] || hard=$(( started + 3600 ))
  if [ "${hard}" -le "${started}" ]; then
    echo "[tertiary] scrub skipped, no time left inside the stage timeout"
    backup_scrub_document "skipped" true "${started}" 0 0 0 0 0
    return 0
  fi
  echo "[tertiary] scrub ${action} on [/backup] until [$(date --iso-8601=seconds -d @"${hard}")]"
  if ! btrfs scrub "${action}" -c 3 -n 15 /backup >/dev/null 2>&1; then
    echo "[tertiary] could not ${action} the scrub on [/backup]" >&2
    backup_scrub_document "failed" false "${started}" 0 0 0 0 0
    return 1
  fi
  while :; do
    sleep "${BACKUP_SCRUB_POLL}"
    raw="$(btrfs scrub status -R /backup 2>/dev/null)"
    printf '%s\n' "${raw}" | grep -qi "status:[[:space:]]*running" || break
    if [ "$(date +%s)" -ge "${hard}" ]; then
      btrfs scrub cancel /backup >/dev/null 2>&1 || true
      state="interrupted"
      break
    fi
  done
  raw="$(btrfs scrub status -R /backup 2>/dev/null)"
  status="$(btrfs scrub status /backup 2>/dev/null)"
  scrubbed=$(( $(backup_scrub_counter "${raw}" "data_bytes_scrubbed") / 1048576 ))
  corrected="$(backup_scrub_counter "${raw}" "corrected_errors")"
  uncorrectable="$(backup_scrub_counter "${raw}" "uncorrectable_errors")"
  found=$(( $(backup_scrub_counter "${raw}" "csum_errors") +
    $(backup_scrub_counter "${raw}" "verify_errors") +
    $(backup_scrub_counter "${raw}" "super_errors") ))
  progress="$(printf '%s\n' "${status}" | sed -n 's/.*(\([0-9.]*\)%).*/\1/p' | head -1)"
  progress="${progress:-0}"
  case "${status}" in
  *aborted*) state="failed" ;;
  *interrupted*) state="interrupted" ;;
  esac
  if [ "${found}" -gt 0 ] || [ "${uncorrectable}" -gt 0 ]; then
    success=false
    {
      printf '%s\n\n' "${raw}"
      dmesg -T 2>/dev/null | grep -iE 'btrfs.*(csum|checksum|unable to fixup)' | tail -500
    } >"${BACKUP_STAGE_DIR}/scrub.log"
    echo "[tertiary] scrub found [${found}] error(s) with [${uncorrectable}] uncorrectable, corrupt files listed in [${BACKUP_STAGE_DIR}/scrub.log]" >&2
  else
    echo "[tertiary] scrub ${state} at [${progress}] pct having scrubbed [${scrubbed}] MB with no errors"
  fi
  backup_scrub_document "${state}" "${success}" "${started}" "${scrubbed}" "${progress}" "${found}" "${corrected}" "${uncorrectable}"
  [ "${success}" = "true" ]
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
    find "${target}/.rsync" -mindepth 1 -mtime +7 -delete 2>/dev/null
    echo "[tertiary] mirroring [${share}] to [${target}]"
    local output
    output="$(rsync -a --delete --stats --exclude '/tmp/' --exclude '/.rsync/' \
      --partial-dir="${target}/.rsync" -- "${share}/" "${target}/" 2>&1)" || failed=1
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
    backup_scrub || failed=1
    backup_usage /backup
  fi
  stage_stop || true
  return "${failed}"
}

stage_stop() {
  backup_scrub_cancel
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
