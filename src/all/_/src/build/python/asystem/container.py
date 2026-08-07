import os
import stat
import sys
from os.path import *

from pathlib2 import Path


def write_container_bootstrap(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources/image")
    path_bootstrap = join(root_dir, "src/build/resources/bootstrap.sh")
    if not isfile(path_bootstrap):
        os.makedirs(os.path.dirname(path_bootstrap), exist_ok=True)
        Path(path_bootstrap).write_text("# TODO: Provide implementation\necho ''\n")
    script_bootstrap = Path(path_bootstrap).read_text().strip()
    os.makedirs(working_dir, exist_ok=True)
    script_path = abspath(join(working_dir, "bootstrap.sh"))
    with open(script_path, 'w') as script_file:
        script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${{ASYSTEM_HOME:-"/asystem/etc"}}

MESSAGE="Waiting for service to come alive ... "
echo "${{MESSAGE}}"
while ! "${{ASYSTEM_HOME}}/checkalive.sh"; do
 echo "${{MESSAGE}}" && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

{}

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

MESSAGE="Waiting for service to start executing ... "
echo "${{MESSAGE}}"
while ! "${{ASYSTEM_HOME}}/checkexecuting.sh"; do
  echo "${{MESSAGE}}" && sleep 1
done
echo "----------" && echo "✅ Service has started"
        """.format(
            script_bootstrap.strip(),
        ).strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(module_name, script_path))


def write_container_healthchecks(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources/image")
    os.makedirs(working_dir, exist_ok=True)
    for script, source in {
        "alive": "true",
        "executing": "/asystem/etc/checkalive.sh \"${POSITIONAL_ARGS[@]}\" && \n  true",
        "healthy": "/asystem/etc/checkexecuting.sh \"${POSITIONAL_ARGS[@]}\" && \n  true",
    }.items():
        script_source_path = join(root_dir, "src/build/resources/check{}.sh".format(script))
        if not isfile(script_source_path):
            os.makedirs(os.path.dirname(script_source_path), exist_ok=True)
            Path(script_source_path).write_text(source + "\n# TODO: Provide implementation\n")
        script_source = " ".join([line.strip() for line in Path(script_source_path).read_text().strip().split("\n")])
        script_path = abspath(join(working_dir, "check{}.sh".format(script)))
        with open(script_path, 'w') as script_file:
            script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

POSITIONAL_ARGS=()
HEALTHCHECK_VERBOSE=${{HEALTHCHECK_VERBOSE:-false}}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    HEALTHCHECK_VERBOSE=true
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${{0}} [-v|--verbose] [-h|--help] [alive]"
    exit 2
    ;;
  *)
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  esac
done

if [ "${{HEALTHCHECK_VERBOSE}}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -x
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

shopt -s expand_aliases

if
  {}
then
  set +x
  [ "${{HEALTHCHECK_VERBOSE}}" == true ] && echo "✅ The service [{}] is {} :)" >&2
  exit 0
else
  set +x
  [ "${{HEALTHCHECK_VERBOSE}}" == true ] && echo "❌ The service [{}] is *NOT* {} :(" >&2
  exit 1
fi
            """.format(
                script_source,
                module_name,
                script,
                module_name,
                script,
            ).strip() + "\n")
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
        print("Build generate script [{}] script persisted to [{}]"
              .format(module_name, script_path))


def write_container_certificates(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources/image")
    os.makedirs(working_dir, exist_ok=True)
    script_path = abspath(join(working_dir, "certificates.sh"))
    with open(script_path, 'w') as script_file:
        script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <mode> <host-pull> <host-push>"
  exit 1
fi
if [ "$1" = "pull" ]; then
  echo "Pulling certificates ..."
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/privkey.pem" "$ROOT_DIR/.key.pem"
  scp -q -o "StrictHostKeyChecking=no" -pr "root@$2:/home/asystem/letsencrypt/latest/certificates/fullchain.pem" "$ROOT_DIR/certificate.pem"
  echo "$2:/home/asystem/letsencrypt/latest/certificates -> localhost:$ROOT_DIR"
  echo "Pulling certificates ... done"
elif [ "$1" = "push" ]; then
  echo "Pushing certificates ..."
  for DIR in "/home/asystem/{}/latest" "/var/lib/asystem/install/{}/latest/data"; do
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/.key.pem" "root@$3:$DIR"
    scp -q -o "StrictHostKeyChecking=no" -pr "$ROOT_DIR/certificate.pem" "root@$3:$DIR"
    echo "localhost:$ROOT_DIR -> $3:$DIR"
  done
  echo "Restarting service on [$3] ... "
  ssh -q -o "StrictHostKeyChecking=no" "root@$3" "/var/lib/asystem/install/{}/latest/install.sh"
  echo "Pushing certificates ... done"
fi
exit 0
        """.format(
            module_name,
            module_name,
            module_name,
        ).strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(module_name, script_path))


def write_container_volumes():
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    script_path = join(root_dir, "src/main/resources/volumes.sh")
    if not isdir(dirname(script_path)):
        os.makedirs(dirname(script_path), exist_ok=True)
    with open(script_path, 'w') as script_file:
        script_file.write("""
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
diff -uw /etc/fstab.bak /etc/fstab
for _smb in smb.service smbd.service; do ! systemctl list-unit-files ${_smb} | grep -q masked && systemctl is-active --quiet ${_smb} && systemctl stop ${_smb}; done
for _dir in /share /backup; do mkdir -p "${_dir}" && chmod 750 "${_dir}" && chown graham:users "${_dir}"; done
for _dir in $(mount | grep '/share\\|/backup' | awk '{print $3}'); do umount -f "${_dir}"; done
[ "$(find /share /backup -mindepth 2 -maxdepth 2 | wc -l)" -gt 0 ] && {
  echo && echo "❌ Could not unmount all shares" && echo
  exit 1
}
find /share -mindepth 1 -maxdepth 1 -type d -empty -delete
find /backup -mindepth 1 -maxdepth 1 -type d -empty -delete
for _dir in $(grep -v '^#' /etc/fstab | grep '/share\\|/backup' | awk '{print $2}'); do mkdir -p "${_dir}" && chmod 750 "${_dir}" && chown graham:users "${_dir}"; done
for _smb in smb.service smbd.service; do systemctl list-unit-files ${_smb} | grep -q ${_smb} && ! systemctl list-unit-files ${_smb} | grep -q masked && ! systemctl is-active --quiet ${_smb} && systemctl start ${_smb}; done
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
for share_automount_unit in $(systemctl list-units --type=automount --no-legend | grep 'share-' | awk '/share-[0-9]+\\.automount$/ {print $2}'); do
  systemctl stop "$share_automount_unit"
  systemctl disable "$share_automount_unit"
done
systemctl daemon-reload
systemctl reset-failed
echo && echo "✅ Volumes configured" && echo
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
while read dev size tran; do
  for part in $(lsblk -ln -o NAME /dev/$dev | tail -n +2); do
    mp=$(findmnt -nr -S /dev/$part -o TARGET)
    [[ -z "$mp" ]] || [[ "$mp" == /boot* ]] && continue
    dev_num=$(udevadm info --query=property --name=/dev/$part | grep DEVPATH | sed -n 's|.*/usb\\([0-9]\\+\\)/.*|\\1|p')
    speed=$(lsusb -t | grep -E "Bus 0*$dev_num" -A1 | grep -Eo '10000M|5000M|480M|12M' | head -n1)
    case $speed in
    10000M) speed_h="USB 3.1 (10 Gbps)" ;;
    5000M) speed_h="USB 3.0 (5 Gbps)" ;;
    480M) speed_h="USB 2.0 (0.5 Gbps)" ;;
    12M) speed_h="USB 1.1 (0.01 Gbps)" ;;
    *) speed_h="Unknown" ;;
    esac
    dev="/dev/${part%%[0-9]*}"
    devices[$dev]="size=$size;mount=$mp;interface=$speed_h"
  done
done < <(lsblk -o NAME,SIZE,TRAN -nr | grep usb)
while read -r dev size; do
  model=$(smartctl -i "$dev" 2>/dev/null | awk -F: '/Device Model|Model Number/ {gsub(/^[ \\t]+|[ \\t]+$/,"",$2); print $2}')
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
    errors=$(smartctl -a "$dev" 2>/dev/null | awk '$1==1 {print $10}')
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
  tbw="${tbw}T"
  rating="${rating}T"
  life="${life}%"
  if [[ ! "${devices[$dev]}" =~ "model=" ]]; then
    devices[$dev]+="${devices[$dev]:+;}model=$model;tbw=${tbw:-N/A};errors=${errors:-0};rating=$rating;life=$life"
  fi
done < <(lsblk -ndo NAME,TYPE,SIZE | awk '$2=="disk"{print "/dev/"$1, $3}')
for dev in "${!devices[@]}"; do
  IFS=';' read -r -a attrs <<<"${devices[$dev]}"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    if [[ $key == "mount" && $value == "Not Mounted" ]]; then
      unset devices[$dev]
      break
    fi
    if [[ $key == "mount" && $value == "/" ]]; then
      mount="/"
      if [ $(grep /dev /etc/fstab | grep /share | wc -l) -gt 0 ]; then
        mount="$(grep /dev /etc/fstab | grep /share | awk '{print $2}')"
      fi
      devices[$dev]=${devices[$dev]/mount=\\//mount=$mount}
    fi
  done
done
for dev in "${!devices[@]}"; do
  IFS=';' read -r -a attrs <<<"${devices[$dev]}"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    if [[ $key == "mount" ]]; then
      if [ "$value" == "/" ]; then
        label="<NONE>"
      else
        label=$(basename $(grep $value /etc/fstab | awk '{print $1}' | sed 's/PARTLABEL=//') | sed 's/.*-//')
      fi
      devices[$dev]="label=${label}${devices[$dev]:+;${devices[$dev]}}"
    fi
  done
done
declare -a ATTR_ORDER=(label mount model size interface tbw errors rating life)
echo "+------------------------------------------------------------------------------------------------+"
echo "Devices mounted:"
echo "+------------------------------------------------------------------------------------------------+"
for dev in $(printf '%s\n' "${!devices[@]}" | sort -t= -k2 -V); do
  echo "device: $dev"
  for attr in "${ATTR_ORDER[@]}"; do
    if [[ "${devices[$dev]}" =~ "$attr="([^;]+) ]]; then
      value="${BASH_REMATCH[1]}"
      echo "$attr: $value" 
    fi
  done
  echo "+------------------------------------------------------------------------------------------------+"
done
echo
        """.strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(basename(root_dir), script_path))
