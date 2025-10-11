#!/bin/bash

set -e

# Drive Total Bytes Written (TBW) rating in TB
declare -A ratings=(
  ["Lexar SSD NM790 4TB"]=3000
  ["CT4000MX500SSD1"]=1000
  ["CT4000P3PSSD8"]=800
  ["CT2000MX500SSD1"]=700
  ["Lexar SSD NQ710 2TB"]=680
  ["CT2000P2SSD8"]=400
  ["CT1000MX500SSD1"]=360
  ["APPLE SSD AP0512Z"]=300
  ["CT500MX500SSD1"]=180
  ["KINGSTON SA400S37480G"]=160
  ["CT480BX500SSD1"]=120
  ["ST2000LM007-1R8174"]=NA
)
declare -A devices=()

# Collect DAS devices
while read -r name type size tran mountpoint; do
  [[ "$type" != "disk" ]] && continue
  [[ "$tran" == "usb" ]] && continue
  dev="/dev/${name%%n[0-9]*}"
  if [[ "$tran" == "nvme" ]]; then
    mountpoint="/"
    if [[ -f "/proc/device-tree/model" ]] && grep -q "Apple Mac mini (M2 Pro, 2023)" "/proc/device-tree/model"; then
      size=$(df -h / | awk 'NR==2 {print $2}')
      iface="NVMe 16.0 GT/s x4 (63 Gbps)"
    elif [[ -f "/sys/class/dmi/id/product_name" ]] && grep -q "Macmini7,1" "/sys/class/dmi/id/product_name"; then
      iface="NVMe 2.5 GT/s x2 (8 Gbps)"
    fi
  elif [[ "$tran" == "sata" ]]; then
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
    dev_num=$(udevadm info --query=property --name=/dev/$part | grep DEVPATH | sed -n 's|.*/usb\([0-9]\+\)/.*|\1|p')
    speed=$(lsusb -t | grep -E "Bus 0*$dev_num" -A1 | grep -Eo '10000M|5000M|480M|12M' | head -n1)
    case $speed in
    10000M) speed_h="USB 3.1 Gen 2 (10 Gbps)" ;;
    5000M) speed_h="USB 3.0 Gen 1 (5 Gbps)" ;;
    480M) speed_h="USB 2.0 (0.5 Gbps)" ;;
    12M) speed_h="USB 1.1 (0.01 Gbps)" ;;
    *) speed_h="Unknown" ;;
    esac
    dev="/dev/${part%%[0-9]*}"
    devices[$dev]="size=$size;mount=$mp;interface=$speed_h"
  done
done < <(lsblk -o NAME,SIZE,TRAN -nr | grep usb)

# Collect lifetime data
while read -r dev size; do
  model=$(smartctl -i "$dev" 2>/dev/null | awk -F: '/Device Model|Model Number/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2}')
  if [[ -z "$model" ]]; then
    devices[$dev]+="${devices[$dev]:+;}smart=unavailable"
    continue
  fi
  rating="${ratings["$model"]}"
  if smartctl -i "$dev" 2>/dev/null | grep -qi nvme; then
    tbw=$(smartctl -a "$dev" 2>/dev/null | awk -F'[][]' '/Data Units Written:/ {gsub(/,/,"",$2); print $2}')
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '/Error Information Log Entries:/ {print $6}')
  else
    tbw=$(smartctl -a "$dev" 2>/dev/null | awk '$1 == 241 {printf "%.3f", $10/1e3}')
    if [ -z "$tbw" ]; then
      tbw=$(smartctl -a "$dev" 2>/dev/null | awk '$1 == 246 {printf "%.3f", $10*512/1e12}')
    fi
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '$1==1 {$10}')
  fi
  life=""
  if [[ "$tbw" == *GB ]]; then
    tbw=${tbw%GB}
    tbw=${tbw// /}
    tbw=$(awk -v t="$tbw" 'BEGIN{printf "%.3f", t/1000}')
  fi
  tbw=${tbw%TB}
  tbw=${tbw// /}
  if [[ -n $rating && $rating != "NA" && -n $tbw ]]; then
    life=$(awk -v t="$tbw" -v r="$rating" 'BEGIN{printf "%.2f", t/r*100}')
  fi
  dev="${dev%%n[0-9]*}"
  if [[ ! "${devices[$dev]}" =~ "model=" ]]; then
    devices[$dev]+="${devices[$dev]:+;}model=$model;tbw=${tbw:-N/A};errors=${errors:-0};rating=$rating;life=$life"
  fi
done < <(lsblk -ndo NAME,TYPE,SIZE | awk '$2=="disk"{print "/dev/"$1, $3}')

echo && echo && echo
for dev in "${!devices[@]}"; do
  IFS=';' read -r -a attrs <<<"${devices[$dev]}"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    if [[ $key == "mount" && $value != "Not Mounted" ]]; then
      echo "$dev:"
      IFS=';' read -r -a attrs <<<"${devices[$dev]}"
      for attr in "${attrs[@]}"; do
        echo "  ${attr%%=*}: ${attr#*=}"
      done
      echo
    fi
  done
done
echo && echo
