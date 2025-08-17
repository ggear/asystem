#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

fstab_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fstab"
if [ ! -f "$fstab_file" ]; then
  echo && echo "❌ Could not find fstab file [${fstab_file}]" && echo
  exit 1
fi
[ ! -f /etc/fstab.bak ] && cp -v /etc/fstab /etc/fstab.bak
cp -rvf "$fstab_file" /etc/fstab
diff -u /etc/fstab.bak /etc/fstab
! systemctl list-unit-files smbd.service | grep -q masked && systemctl is-active --quiet smbd && systemctl stop smbd
for _dir in /share /backup; do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
for _dir in $(mount | grep '/share\|/backup' | awk '{print $3}'); do umount -f ${_dir}; done
[ "$(find /share /backup -mindepth 2 -maxdepth 2 | wc -l)" -gt 0 ] && {
  echo && echo "❌ Could not unmount all shares" && echo
  exit 1
}
find /share -mindepth 1 -maxdepth 1 -type d -empty -delete
find /backup -mindepth 1 -maxdepth 1 -type d -empty -delete
for _dir in $(grep -v '^#' /etc/fstab | grep '/share\|/backup' | awk '{print $2}'); do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
! systemctl list-unit-files smbd.service | grep -q masked && ! systemctl is-active --quiet smbd && systemctl start smbd
if mount -a 2>/tmp/mount_errors.log; then
  echo "All /etc/fstab entries mounted successfully"
else
  echo "Errors encountered mounting /etc/fstab entries:"
  cat /tmp/mount_errors.log
fi
[ "$(find /share -mindepth 1 -maxdepth 1)" ] && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage,filesystem /share/*
mount -a -O noauto
[ "$(find /backup -mindepth 2 -maxdepth 2)" ] && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage,filesystem /backup/*
awk '$4 ~ /noauto/ {print $2}' /etc/fstab | while read mp; do mountpoint -q "$mp" && umount -f "$mp"; done
systemctl daemon-reload
for share_automount_unit in $(systemctl list-units --type=automount --no-legend | grep 'share-' | awk '/share-[0-9]+\.automount$/ {print $2}'); do
  systemctl stop "$share_automount_unit"
  systemctl disable "$share_automount_unit"
done
systemctl daemon-reload
systemctl reset-failed

echo && echo "✅ Volumes configured" && echo

declare -A ratings=(
  ["CT4000MX500SSD1"]=1000
  ["CT2000MX500SSD1"]=700
  ["CT1000MX500SSD1"]=360
  ["CT500MX500SSD1"]=180
  ["CT480BX500SSD1"]=120
  ["CT4000P3PSSD8"]=800
  ["CT2000P2SSD8"]=400
  ["ST2000LM007-1R8174"]=NA
)
declare -A devices=()

# Collect DAS devices
while read -r name type size tran mountpoint; do
  [[ "$type" != "disk" ]] && continue
  [[ "$tran" == "usb" ]] && continue
  dev="/dev/$name"

  # Hardcoded to Macmini 2014
  if [[ "$tran" == "nvme" ]] || [[ "$name" =~ ^nvme ]]; then
    iface="NVMe 2.5 GT/s x2 (8 Gbps)"
    mountpoint="/"
  else
    iface="SATA III (6 Gbps)"
    mountpoint=$(mount | grep "^$dev" | awk '{print $3}')
  fi
  mountpoint=${mountpoint:-"Not Mounted"}
  devices[$dev]="size=$size;mount=$mountpoint;interface=$iface"
done < <(lsblk -ndo NAME,TYPE,SIZE,TRAN,MOUNTPOINT)

# Collect USB devices
while read dev size tran; do
  for part in $(lsblk -ln -o NAME /dev/$dev | tail -n +2); do
    mp=$(findmnt -nr -S /dev/$part -o TARGET)
    [[ -z "$mp" ]] || [[ "$mp" == /boot* ]] && continue
    speed=$(lsusb -t | grep -Eo '5000M|480M|12M' | head -n1)
    case $speed in
    5000M) speed_h="USB 3.0 (5 Gbps)" ;;
    480M) speed_h="USB 2.0 (4,8 Gbps)" ;;
    12M) speed_h="USB 1.1 (0.12 Gbps)" ;;
    *) speed_h="Unknown" ;;
    esac
    dev="/dev/${part%%[0-9]*}"
    devices[$dev]="size=$size;mount=$mp;interface=$speed_h"
  done
done < <(lsblk -o NAME,SIZE,TRAN -nr | grep usb)

# Collect lifetime data
while read -r dev size; do
  model=$(smartctl -i "$dev" 2>/dev/null | awk -F: '/Device Model|Model Number/ {gsub(/^[ 	]+|[ 	]+$/,"",$2); print $2}')
  if [[ -z "$model" ]]; then
    devices[$dev]+="${devices[$dev]:+;}smart=unavailable"
    continue
  fi
  rating="${ratings["$model"]}"
  if smartctl -i "$dev" 2>/dev/null | grep -qi nvme; then
    tbw=$(smartctl -a "$dev" 2>/dev/null | awk -F'[][]' '/Data Units Written:/ {gsub(/,/,"",$2); print $2}')
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '/Error Information Log Entries:/ {print $6}')
  elif smartctl -i "$dev" 2>/dev/null | grep -qi "SSD"; then
    tbw=$(smartctl -a "$dev" 2>/dev/null | awk '$1 == 246 {printf "%.3f", ($10 * 512)/1e12}')
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '$1==5 || $1==197 || $1==198 || $1==187 {sum+=$10} END{print sum+0}')
  else
    tbw=$(smartctl -a "$dev" 2>/dev/null | awk '$1 == 241 {printf "%.3f", ($10 * 512)/1e12}')
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '$1==5 || $1==197 || $1==198 || $1==187 {sum+=$10} END{print sum+0}')
  fi
  life=""
  if [[ -n $rating && $rating != "NA" && -n $tbw ]]; then
    life=$(awk -v t="$tbw" -v r="$rating" 'BEGIN{printf "%.2f", t/r*100}')
  fi
  devices[$dev]+="${devices[$dev]:+;}model=$model;tbw=${tbw:-N/A};errors=${errors:-0};rating=$rating;life=$life"
done < <(lsblk -ndo NAME,TYPE,SIZE | awk '$2=="disk"{print "/dev/"$1, $3}')

# Print all device information
echo && echo && echo
for dev in $(for d in "${!devices[@]}"; do
  IFS=';' read -r -a attrs <<<"${devices[$d]}"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    if [[ $key == "mount" ]]; then
      echo "$value $d"
      break
    fi
  done
done | sort | cut -d' ' -f2); do
  IFS=';' read -r -a attrs <<<"${devices[$dev]}"
  echo "$dev:"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    case $key in
    size) echo "  Size: $value" ;;
    mount) echo "  Mount: $value" ;;
    interface) echo "  Interface: $value" ;;
    model) echo "  Model: $value" ;;
    tbw) echo "  TBW: $value TB" ;;
    errors) echo "  SMART Errors: $value" ;;
    rating) [[ $value != "NA" ]] && echo "  Rated TBW: $value TB" ;;
    life) [[ -n $value ]] && echo "  Life Used: $value%" ;;
    smart) [[ $value == "unavailable" ]] && echo "  SMART: Unavailable" ;;
    esac
  done
  echo
done
echo && echo