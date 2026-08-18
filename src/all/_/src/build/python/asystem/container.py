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



def write_container_backup(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources")
    os.makedirs(working_dir, exist_ok=True)
    script_source_path = join(root_dir, "src/build/resources/backup.sh")
    if not isfile(script_source_path):
        os.makedirs(os.path.dirname(script_source_path), exist_ok=True)
        Path(script_source_path).write_text("""# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this and came from the same version
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself

# TODO: Provide implementation

backup_written() {
  backup_files "relative/path:another/path"
}

# A module with its own backup mechanism names its backup, then writes it:
#
# backup_written() {
#   backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
#   docker exec --user root "${BACKUP_MODULE_NAME}" bash -c 'dump | gzip' >"${BACKUP_TARGET_PATH}.tmp"
# }
""")
    script_source = Path(script_source_path).read_text().strip()
    script_path = abspath(join(working_dir, "backup.sh"))
    with open(script_path, 'w') as script_file:
        script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# The wrapper owns the run, the module snippet owns the backup. The wrapper checks the throttle,
# calls backup_written, renames the temporary file on success, prunes and sets the exit code. The
# snippet defines backup_written, which names its backup with backup_target (or lets backup_files
# do both) and writes "${{BACKUP_TARGET_PATH}}.tmp". Nothing else crosses the line: a snippet never
# assigns a wrapper variable, and the wrapper never reads a snippet one.
#
# BACKUP_*           vars owned by the wrapper for the snippet to read, never assigned by a snippet
# BACKUP_INTERNAL_*  vars owned by the wrapper for its internal use
# <MODULE>_*         vars owned by a snippet, prefixed with its module name to avoid collisions with wrapper vars
#
# A snippet needing a value from .env expands it with "${{VAR:?}}", so a renamed or missing key
# fails by name rather than producing an empty argument and a corrupt backup.

BACKUP_INTERNAL_ENV="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)/.env"
[ -f "${{BACKUP_INTERNAL_ENV}}" ] && . "${{BACKUP_INTERNAL_ENV}}"

BACKUP_MODULE_NAME="{module}"
BACKUP_SOURCE_PATH="${{BACKUP_SOURCE_PATH:-${{SERVICE_DATA_DIR:-/home/asystem/{module}/latest}}}}"
BACKUP_INTERNAL_SOURCE_DIR="$(readlink -f "${{BACKUP_SOURCE_PATH}}")"
BACKUP_SOURCE_VERSION="$(basename "${{BACKUP_INTERNAL_SOURCE_DIR}}")"
BACKUP_INTERNAL_ROOT_DIR="$(dirname "${{BACKUP_INTERNAL_SOURCE_DIR}}")/backup"
BACKUP_RUN_TIMESTAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_FULL_SUFFIX="_full"
BACKUP_DELTA_SUFFIX="_delta"
BACKUP_RETAIN_DAYS="${{BACKUP_RETAIN_DAYS:-7}}"
BACKUP_SKIP_HOURS="${{BACKUP_SKIP_HOURS:-1}}"
BACKUP_SERVICE_RESTART="${{BACKUP_SERVICE_RESTART:-true}}"
BACKUP_TARGET_PATH=""

BACKUP_INTERNAL_NEWEST=""
BACKUP_INTERNAL_NEWEST_VERSION=""
BACKUP_INTERNAL_SIZE=0
BACKUP_INTERNAL_STARTED=0
BACKUP_INTERNAL_STATUS=0

backup_target() {{
  local suffix="${{1:-}}" extension="${{2:-}}"
  if [ -z "${{suffix}}" ] || [ -z "${{extension}}" ]; then
    echo "Cannot name the backup, pass the suffix and the extension to backup_target" >&2
    return 1
  fi
  BACKUP_TARGET_PATH="${{BACKUP_INTERNAL_ROOT_DIR}}/${{BACKUP_RUN_TIMESTAMP}}/${{BACKUP_MODULE_NAME}}_${{BACKUP_RUN_TIMESTAMP}}_${{BACKUP_SOURCE_VERSION}}${{suffix}}.${{extension}}"
  mkdir -p "$(dirname "${{BACKUP_TARGET_PATH}}")"
}}

backup_is_full() {{ [[ "${{1}}" == *"${{BACKUP_FULL_SUFFIX}}".* ]]; }}

backup_is_delta() {{ [[ "${{1}}" == *"${{BACKUP_DELTA_SUFFIX}}".* ]]; }}

backup_discarded() {{
  [ -n "${{BACKUP_TARGET_PATH}}" ] || return 0
  rm -f "${{BACKUP_TARGET_PATH}}.tmp"
  [ -e "${{BACKUP_TARGET_PATH}}" ] || rmdir "$(dirname "${{BACKUP_TARGET_PATH}}")" 2>/dev/null
}}

backup_epoch() {{
  local stamp="${{1: -19}}"
  date -d "${{stamp:0:10}} ${{stamp:11:2}}:${{stamp:14:2}}:${{stamp:17:2}}" +%s 2>/dev/null || echo 0
}}

backup_listed() {{
  local dir="${{1:-${{BACKUP_INTERNAL_ROOT_DIR}}}}"
  [ -d "${{dir}}" ] || return 0
  find "${{dir}}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}_[0-9]{{2}}-[0-9]{{2}}-[0-9]{{2}}$' | sort
}}

backup_versioned() {{
  local stamp="${{1:-}}" dir="${{2:-${{BACKUP_INTERNAL_ROOT_DIR}}}}" path name
  [ -n "${{stamp}}" ] || return 0
  for path in "${{dir}}/${{stamp}}"/*; do
    [ -f "${{path}}" ] || continue
    name="$(basename "${{path}}")"
    name="${{name#"${{BACKUP_MODULE_NAME}}_${{stamp}}_"}}"
    name="${{name%"${{BACKUP_FULL_SUFFIX}}".*}}"
    name="${{name%"${{BACKUP_DELTA_SUFFIX}}".*}}"
    printf '%s\n' "${{name}}"
    return 0
  done
}}

backup_healthy() {{
  local dir="${{1:-${{BACKUP_INTERNAL_ROOT_DIR}}}}" elapsed=3600 names
  mapfile -t names < <(backup_listed "${{dir}}")
  [ "${{#names[@]}}" -gt 0 ] || return 1
  [ $(($(date +%s) - $(backup_epoch "${{names[-1]}}"))) -lt $((86400 + elapsed)) ]
}}

backup_pruned() {{
  local dir="${{1:-${{BACKUP_INTERNAL_ROOT_DIR}}}}" names index cutoff
  mapfile -t names < <(backup_listed "${{dir}}")
  [ "${{#names[@]}}" -gt 1 ] || return 0
  cutoff=$(($(date +%s) - BACKUP_RETAIN_DAYS * 86400))
  for ((index = 0; index < ${{#names[@]}} - 1; index++)); do
    if [ "$(backup_epoch "${{names[${{index}}]}}")" -lt "${{cutoff}}" ]; then
      rm -rf "${{dir:?}}/${{names[${{index}}]}}"
      echo "Deleted backup [${{names[${{index}}]}}] older than [${{BACKUP_RETAIN_DAYS}}] days"
    fi
  done
}}

backup_included() {{
  local path
  while IFS= read -r -d ':' path || [ -n "${{path}}" ]; do
    [ -n "${{path}}" ] || continue
    if [ -e "${{BACKUP_SOURCE_PATH}}/${{path}}" ]; then
      printf '%s\n' "${{path}}"
    else
      echo "Declared path [${{path}}] is absent from [${{BACKUP_SOURCE_PATH}}]" >&2
    fi
  done < <(printf '%s:' "${{1}}")
}}

backup_unmatched() {{
  local entry path matched includes
  mapfile -t includes < <(backup_included "${{1}}" 2>/dev/null)
  while IFS= read -r entry; do
    [ "${{entry}}" = "backup" ] && continue
    matched=""
    for path in "${{includes[@]}}"; do
      case "${{path}}" in "${{entry}}" | "${{entry}}/"*) matched=1 ;; esac
    done
    [ -n "${{matched}}" ] || printf '%s\n' "${{entry}}"
  done < <(find "${{BACKUP_SOURCE_PATH}}" -maxdepth 1 -mindepth 1 -printf '%f\n' 2>/dev/null | sort)
}}

backup_files() {{
  local declared="${{1:-}}" paths unmatched
  if [ -z "${{declared}}" ]; then
    echo "Nothing to back up, pass the paths to copy to backup_files" >&2
    return 1
  fi
  mapfile -t paths < <(backup_included "${{declared}}")
  if [ "${{#paths[@]}}" -eq 0 ]; then
    echo "No declared path exists under [${{BACKUP_SOURCE_PATH}}]" >&2
    return 1
  fi
  backup_target "${{BACKUP_FULL_SUFFIX}}" "${{2:-tar.gz}}" || return 1
  mapfile -t unmatched < <(backup_unmatched "${{declared}}")
  [ "${{#unmatched[@]}}" -gt 0 ] && echo "Not backed up, no declared path covers [${{unmatched[*]}}]"
  tar --create --directory "${{BACKUP_SOURCE_PATH}}" --numeric-owner --preserve-permissions \
    --exclude=backup --file - -- "${{paths[@]}}" 2>/dev/null | gzip >"${{BACKUP_TARGET_PATH}}.tmp"
}}

backup_written() {{
  echo "Nothing to back up, define backup_written in the module snippet" >&2
  return 1
}}

{source}

[ "${{BASH_SOURCE[0]}}" = "${{0}}" ] || return 0

if [ "${{1:-}}" = "--prune" ]; then
  backup_pruned "${{2}}"
  exit 0
fi

find "${{BACKUP_INTERNAL_ROOT_DIR}}" -type f -name '*.tmp' -delete 2>/dev/null

mapfile -t BACKUP_INTERNAL_EXISTING < <(backup_listed)
if [ "${{#BACKUP_INTERNAL_EXISTING[@]}}" -gt 0 ]; then
  BACKUP_INTERNAL_NEWEST="${{BACKUP_INTERNAL_EXISTING[-1]}}"
  BACKUP_INTERNAL_NEWEST_VERSION="$(backup_versioned "${{BACKUP_INTERNAL_NEWEST}}")"
  BACKUP_INTERNAL_AGE=$(($(date +%s) - $(backup_epoch "${{BACKUP_INTERNAL_NEWEST}}")))
  if [ "${{BACKUP_INTERNAL_AGE}}" -lt $((BACKUP_SKIP_HOURS * 3600)) ] &&
    [ "${{BACKUP_INTERNAL_NEWEST_VERSION}}" = "${{BACKUP_SOURCE_VERSION}}" ]; then
    echo "Backup skipped, newest backup [${{BACKUP_INTERNAL_NEWEST}}] of version [${{BACKUP_INTERNAL_NEWEST_VERSION}}] is [${{BACKUP_INTERNAL_AGE}}] seconds old, skipping given within [${{BACKUP_SKIP_HOURS}}] hours"
    exit 0
  fi
fi

echo "Starting backup from version [${{BACKUP_SOURCE_VERSION}}] holding [${{#BACKUP_INTERNAL_EXISTING[@]}}] backups, newest [${{BACKUP_INTERNAL_NEWEST:-none}}] retaining [${{BACKUP_RETAIN_DAYS}}] days, skipping backup if executing again within [${{BACKUP_SKIP_HOURS}}] hours"

trap backup_discarded EXIT
BACKUP_INTERNAL_STARTED=${{SECONDS}}
if backup_written && [ -n "${{BACKUP_TARGET_PATH}}" ] && [ -s "${{BACKUP_TARGET_PATH}}.tmp" ]; then
  mv "${{BACKUP_TARGET_PATH}}.tmp" "${{BACKUP_TARGET_PATH}}"
  BACKUP_INTERNAL_SIZE="$(du -m "${{BACKUP_TARGET_PATH}}" | cut -f1)"
  echo "Finished backup [${{BACKUP_INTERNAL_SIZE}}] MB in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds to [${{BACKUP_TARGET_PATH}}]"
  backup_pruned
else
  [ -n "${{BACKUP_TARGET_PATH}}" ] || echo "Nothing named the backup, call backup_target in backup_written" >&2
  echo "Failed backup in [$((SECONDS - BACKUP_INTERNAL_STARTED))] seconds" >&2
  BACKUP_INTERNAL_STATUS=1
fi

find "${{BACKUP_INTERNAL_ROOT_DIR}}" -depth -empty -delete -type d
exit "${{BACKUP_INTERNAL_STATUS}}"
""".format(module=module_name, source=script_source).strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(basename(root_dir), script_path))
