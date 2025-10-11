import datetime
import glob
import json
import os
import shutil
import stat
import sys
import time
from collections import OrderedDict
from os.path import *

import pandas as pd
from pathlib2 import Path
from requests import get

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


def load_env(root_dir=None):
    env_load = {}
    env_load_path = abspath(join(DIR_ROOT if root_dir is None else root_dir, ".env"))
    env_load_path_dev = env_load_path
    if not isfile(env_load_path):
        env_load_path = abspath(join(DIR_ROOT if root_dir is None else root_dir, "target/release/.env"))
    if not isfile(env_load_path):
        raise Exception("Could not find dev [{}] or prod [{}] env file".format(env_load_path_dev, env_load_path))
    with open(env_load_path, 'r') as env_file:
        for env_load_line in env_file:
            env_load_line = env_load_line.replace("export ", "").rstrip()
            if "=" not in env_load_line:
                continue
            if env_load_line.startswith("#"):
                continue
            env_load_key, env_load_value = env_load_line.split("=", 1)
            env_load[env_load_key] = env_load_value
    print("Build generate script environment loaded from [{}]".format(env_load_path))
    sys.stdout.flush()
    return env_load


def load_modules(load_disabled=True, load_infrastrcture=True):
    modules = {}
    host_labels_names = {line.split("=")[0]: line.split("=")[-1].split(",")
                         for line in
                         Path(join(dirname(abspath(join(DIR_ROOT, "../.."))), ".hosts")).read_text().strip().split(
                             "\n")}
    for module in glob.glob(abspath(join(DIR_ROOT, "../../*/*"))):
        group_path = Path(join(module, ".group"))
        if (load_disabled or (isfile(group_path) and group_path.read_text().strip().isdigit() and
                              int(group_path.read_text().strip()) >= 0)) and \
                (load_infrastrcture or not basename(module).startswith("_")):
            env = load_env(module)
            name = basename(module)
            hosts = ["{}-{}".format(host_labels_names[host_label][0], host_label) for host_label in
                     basename(dirname(module)).split("_")]
            modules[name] = [hosts, env]
    return modules


def load_entity_metadata():
    metadata_path = abspath(join(DIR_ROOT, "src/build/resources/entity_metadata.xlsx"))
    metadata_df = pd.read_excel(metadata_path, header=2, dtype=str)
    metadata_df["index"] = metadata_df["index"].astype(int)
    metadata_df = metadata_df.set_index(metadata_df["index"]).sort_index()
    print("Build generate script entity metadata loaded from [{}]".format(metadata_path))
    sys.stdout.flush()
    return metadata_df


def write_certificates(module_name=None, working_dir=None):
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


def write_volumes():
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
for _dir in /share /backup; do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
for _dir in $(mount | grep '/share\\|/backup' | awk '{print $3}'); do umount -f ${_dir}; done
[ "$(find /share /backup -mindepth 2 -maxdepth 2 | wc -l)" -gt 0 ] && {
  echo && echo "❌ Could not unmount all shares" && echo
  exit 1
}
find /share -mindepth 1 -maxdepth 1 -type d -empty -delete
find /backup -mindepth 1 -maxdepth 1 -type d -empty -delete
for _dir in $(grep -v '^#' /etc/fstab | grep '/share\\|/backup' | awk '{print $2}'); do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
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
  tbw="${tbw}T"
  rating="${rating}T"
  life="${life}%"
  if [[ ! "${devices[$dev]}" =~ "model=" ]]; then
    devices[$dev]+="${devices[$dev]:+;}model=$model;tbw=${tbw:-N/A};errors=${errors:-0};rating=$rating;life=$life"
  fi
done < <(lsblk -ndo NAME,TYPE,SIZE | awk '$2=="disk"{print "/dev/"$1, $3}')
echo && echo "Devices mounted:" && echo
for dev in "${!devices[@]}"; do
  IFS=';' read -r -a attrs <<<"${devices[$dev]}"
  for attr in "${attrs[@]}"; do
    key="${attr%%=*}"
    value="${attr#*=}"
    if [[ $key == "mount" && $value != "Not Mounted" ]]; then
        
        if [ "$value" == "/" ]; then
            label="TODO"
        else
            label=$(basename $(grep $value /etc/fstab | awk '{print $1}' | sed 's/PARTLABEL=//') | sed 's/.*-//')
        fi
        devices[$dev]="label=${label};mount=WEE${devices[$dev]:+;${devices[$dev]}}"

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
        """.strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(basename(root_dir), script_path))


def write_bootstrap(module_name=None, working_dir=None):
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

MESSAGE="Waiting for service to come alive ..."
echo "${{MESSAGE}}"
while ! "${{ASYSTEM_HOME}}/checkalive.sh"; do
 echo "${{MESSAGE}}" && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

{}

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

set +eo pipefail

MESSAGE="Waiting for service to become ready ..."
echo "${{MESSAGE}}"
while ! "${{ASYSTEM_HOME}}/checkready.sh"; do
  echo "${{MESSAGE}}" && sleep 1
done
echo "----------" && echo "✅ Service has started"
        """.format(
            script_bootstrap.strip(),
        ).strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(module_name, script_path))


def write_healthcheck(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources/image")
    os.makedirs(working_dir, exist_ok=True)
    for script in ["alive", "ready"]:
        script_source_path = join(root_dir, "src/build/resources/check{}.sh".format(script))
        if not isfile(script_source_path):
            os.makedirs(os.path.dirname(script_source_path), exist_ok=True)
            Path(script_source_path).write_text("true\n# TODO: Provide implementation\n")
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
set -- "${{POSITIONAL_ARGS[@]}}"

if [ "${{HEALTHCHECK_VERBOSE}}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

set -eo pipefail
shopt -s expand_aliases

if
  {}
then
  [ "${{HEALTHCHECK_VERBOSE}}" == true ] && echo "✅ The service [{}] is {} :)" >&2
  exit 0
else
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


def write_entity_metadata(module_name, working_dir, metadata_df, topics_discovery, topics_data):
    if len(metadata_df) > 0:
        metadata_df = metadata_df.copy()
        metadata_columns = [column for column in metadata_df.columns if
                            (column.startswith("device_") and column != "device_class")]
        metadata_columns_rename = {column: column.replace("device_", "") for column in metadata_columns}
        if exists(working_dir):
            shutil.rmtree(working_dir)
        for _, row in metadata_df.iterrows():
            metadata_dict = row[[
                "unique_id",
                "name",
                "state_class",
                "unit_of_measurement",
                "device_class",
                "icon",
                "force_update",
                "optimistic",
                "state_topic",
                "value_template",
                "command_topic",
                "availability_topic",
                "payload_on",
                "payload_off",
                "payload_available",
                "payload_not_available",
                "qos",
            ]].dropna().to_dict()
            metadata_unique_id = metadata_dict["unique_id"]
            metadata_dict_clone = {"object_id": metadata_dict["unique_id"]}
            metadata_dict_clone.update(metadata_dict)
            metadata_dict = metadata_dict_clone
            metadata_dict["device"] = row[metadata_columns].rename(metadata_columns_rename).dropna().to_dict()
            if "connections" in metadata_dict["device"]:
                metadata_dict["device"]["connections"] = json.loads(metadata_dict["device"]["connections"])
            metadata_publish_dir = abspath(join(working_dir, row['discovery_topic']))
            os.makedirs(metadata_publish_dir)
            metadata_publish_str = json.dumps(metadata_dict, ensure_ascii=False, indent=2) + "\n"
            metadata_publish_path = abspath(join(metadata_publish_dir, metadata_unique_id + ".json"))
            with open(metadata_publish_path, 'a') as metadata_publish_file:
                metadata_publish_file.write(metadata_publish_str)
                print("Build generate script [{}] entity metadata [sensor.{}] persisted to [{}]"
                      .format(module_name, metadata_unique_id, metadata_publish_path))
        metadata_publish_script_path = abspath(working_dir + ".sh")
        with open(metadata_publish_script_path, 'w') as metadata_publish_script_file:
            metadata_publish_script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname $(readlink -f "$0"))/mqtt"

printf "\\nEntity Metadata publish script [{}] dropping discovery topics:\\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t '{}' -W 1 2>/dev/null

printf "\\nEntity Metadata publish script [{}] sleeping before dropping data topics ... " && sleep 2 && printf "done\\n\\n"

printf "Entity Metadata publish script [{}] dropping data topics:\\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t '{}' -W 1 2>/dev/null

printf "\\nEntity Metadata publish script [{}] sleeping before publishing discovery topics ... " && sleep 2 && printf "done\\n\\n"

printf "Entity Metadata publish script [{}] publishing discovery topics:\\n"
find $ROOT_DIR -name "*.json" -print0 | while read -d $'\\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${{METADATA_FILE/$ROOT_DIR\\//}}")
  mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t $METADATA_TOPIC -f $METADATA_FILE -r
  printf "$METADATA_TOPIC\\n"
done
printf "\\n"
            """.format(
                module_name,
                topics_discovery,
                module_name,
                module_name,
                topics_data,
                module_name,
                module_name,
            ).strip())
        os.chmod(metadata_publish_script_path, 0o750)
        print("Build generate script [{}] entity metadata publish script persisted to [{}]"
              .format(module_name, metadata_publish_script_path))


if __name__ == "__main__":
    env = load_env()
    metadata_hass_df = load_entity_metadata()

    write_bootstrap(working_dir=join(DIR_ROOT, "src/main/resources/data"))
    write_healthcheck(working_dir=join(DIR_ROOT, "src/main/resources/data"))

    # Verify entity IDs
    metadata_verify_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] != "_") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["unique_id"].str.len() > 0)
        ]
    metadata_verify_dicts = [row.dropna().to_dict() for index, row in metadata_verify_df.iterrows()]
    for metadata_verify_dict in metadata_verify_dicts:
        try:
            state_response = get(
                "http://{}:{}/api/states/{}.{}".format(
                    env["HOMEASSISTANT_SERVICE_PROD"],
                    env["HOMEASSISTANT_HTTP_PORT"],
                    metadata_verify_dict["entity_namespace"],
                    metadata_verify_dict["unique_id"]
                ), headers={
                    "Authorization": "Bearer {}".format(env["HOMEASSISTANT_API_TOKEN"]),
                    "content-type": "application/json",
                })
            if state_response.status_code == 200:
                hours_since_update = (time.time() - (time.mktime(datetime.datetime.strptime(
                    state_response.json()["last_updated"].split('+')[0],
                    '%Y-%m-%dT%H:%M:%S.%f').timetuple()) + 8 * 60 * 60)) / (60 * 60)
                if hours_since_update > 6:
                    print(
                        "Build generate script [homeassistant] entity metadata [{}.{}] not recently updated, [{:.1f}] hours"
                        .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"],
                                hours_since_update),
                        file=sys.stderr if \
                            "hass_display_mode" in metadata_verify_dict and \
                            metadata_verify_dict["entity_namespace"] == "sensor"
                        else sys.stdout)
                else:
                    print("Build generate script [homeassistant] entity metadata [{}.{}] verified"
                          .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]))
            else:
                if "hass_display_mode" in metadata_verify_dict and metadata_verify_dict["entity_namespace"] not in [
                    "action"]:
                    print("Build generate script [homeassistant] entity metadata [{}.{}] not found"
                          .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]),
                          file=sys.stderr)
        except Exception as exception:
            print("Build generate script [homeassistant] could not connect to HASS with error [{}]".format(exception))

    # Build customise YAML
    metadata_customise_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] != "_") &
        (metadata_hass_df["device_via_device"] != "Action") &
        (metadata_hass_df["device_via_device"] != "Powercalc Proxy") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["friendly_name"].str.len() > 0) &
        (metadata_hass_df["entity_domain"].str.len() > 0)
        ]
    energy_powercalc_labels = {
        "power": "Current Power",
        "energy": "Total Energy",
    }
    energy_tplink_labels = {
        "current": "Current Amperage",
        "voltage": "Current Voltage",
        "current_consumption": "Current Power",
        "energy": "Total Energy",
        "total_consumption": "Total Energy (Plug)",
        "today_s_consumption": "Total Energy Daily (Plug)",
    }
    energy_meter_labels = {
        "daily": "Total Energy Daily",
        "weekly": "Total Energy Hept-Daily",
        "monthly": "Total Energy Monthly",
        "yearly": "Total Energy Yearly",
    }
    metadata_customise_dicts = [row.dropna().to_dict() for index, row in metadata_customise_df.iterrows()]


    def _add_energy_plug(unique_id, friendly_name, icon=None):
        energy_plug_already_customised = False
        for energy_plug_to_customise in metadata_customise_dicts:
            if unique_id == energy_plug_to_customise["unique_id"]:
                energy_plug_already_customised = True
                break
        if not energy_plug_already_customised:
            energy_plug_dict = {
                "entity_namespace": "sensor",
                "unique_id": unique_id,
                "friendly_name": friendly_name
            }
            if icon is not None:
                energy_plug_dict["icon"] = icon
            metadata_customise_dicts.extend([energy_plug_dict])


    energy_plugs = []
    metadata_customise_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] == "Tasmota")
        ]
    for _, metadata_hass_row in metadata_customise_df.iterrows():
        if metadata_hass_row["unique_id"].endswith("_energy_total"):
            energy_plugs.append(metadata_hass_row["unique_id"].replace("_energy_total", ""))
            for energy_meter_label in energy_meter_labels:
                _add_energy_plug("{}_{}".format(metadata_hass_row["unique_id"], energy_meter_label),
                                 energy_meter_labels[energy_meter_label], "mdi:counter")
    for _, metadata_hass_row in metadata_customise_df.iterrows():
        if metadata_hass_row["entity_namespace"] != "sensor" and metadata_hass_row["unique_id"] not in energy_plugs:
            for energy_sensor_label in energy_powercalc_labels:
                _add_energy_plug("{}_{}".format(metadata_hass_row["unique_id"], energy_sensor_label),
                                 energy_powercalc_labels[energy_sensor_label])
            for energy_meter_label in energy_meter_labels:
                _add_energy_plug("{}_energy_{}".format(metadata_hass_row["unique_id"], energy_meter_label),
                                 energy_meter_labels[energy_meter_label], "mdi:counter")
    metadata_customise_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] == "TPLink")
        ]
    for _, metadata_hass_row in metadata_customise_df.iterrows():
        for energy_sensor_label in energy_tplink_labels:
            _add_energy_plug("{}_{}".format(metadata_hass_row["unique_id"], energy_sensor_label),
                             energy_tplink_labels[energy_sensor_label],
                             "mdi:counter" if energy_sensor_label == "today_s_consumption" else None)
        for energy_meter_label in energy_meter_labels:
            _add_energy_plug("{}_energy_{}".format(metadata_hass_row["unique_id"], energy_meter_label),
                             energy_meter_labels[energy_meter_label], "mdi:counter")
    metadata_customise_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] != "TPLink") &
        (metadata_hass_df["device_via_device"] != "Tasmota") &
        (metadata_hass_df["powercalc_enable"] == "True")
        ]
    for _, metadata_hass_row in metadata_customise_df.iterrows():
        metadata_hass_friendly_name_suffix = ""
        metadata_hass_unique_id = metadata_hass_row["unique_id"]
        if "powercalc_config" in metadata_hass_row and isinstance(metadata_hass_row["powercalc_config"], str):
            if metadata_hass_row["powercalc_config"].startswith("name:"):
                metadata_hass_unique_id_name = metadata_hass_row["powercalc_config"].split("\n")[0].replace("name:", "") \
                    .strip().replace(" ", "_").lower()
                if metadata_hass_unique_id != metadata_hass_unique_id_name:
                    metadata_hass_unique_id = metadata_hass_unique_id_name
                    metadata_hass_friendly_name_suffix = " ({})".format(metadata_hass_row["entity_namespace"].title())
        for energy_sensor_label in energy_powercalc_labels:
            _add_energy_plug("{}_{}".format(metadata_hass_unique_id, energy_sensor_label),
                             energy_powercalc_labels[energy_sensor_label] + metadata_hass_friendly_name_suffix)
        for energy_meter_label in energy_meter_labels:
            _add_energy_plug("{}_energy_{}".format(metadata_hass_unique_id, energy_meter_label),
                             energy_meter_labels[energy_meter_label] + metadata_hass_friendly_name_suffix,
                             "mdi:counter")
    metadata_customise_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["powercalc_enable"] == "True")
        ]
    for _, metadata_hass_row in metadata_customise_df.iterrows():
        for energy_group in [
            "powercalc_group_1",
            "powercalc_group_2",
            "powercalc_group_3",
            "powercalc_group_4",
        ]:
            if energy_group in metadata_hass_row and isinstance(metadata_hass_row[energy_group], str):
                energy_group_unique_id = metadata_hass_row[energy_group].replace(" &", "").replace(" ", "_").lower()
                for energy_sensor_label in energy_powercalc_labels:
                    _add_energy_plug("{}_{}".format(energy_group_unique_id, energy_sensor_label),
                                     "{} {}".format(metadata_hass_row[energy_group],
                                                    energy_powercalc_labels[energy_sensor_label]))
                for energy_meter_label in energy_meter_labels:
                    _add_energy_plug("{}_energy_{}".format(energy_group_unique_id, energy_meter_label),
                                     "{} {}".format(metadata_hass_row[energy_group],
                                                    energy_meter_labels[energy_meter_label],
                                                    "mdi:counter"))
    metadata_customise_path = abspath(join(DIR_ROOT, "src/main/resources/data/customise.yaml"))
    with open(metadata_customise_path, 'w') as metadata_customise_file:
        metadata_customise_file.write("""
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################
        """.strip() + "\n")
        for metadata_customise_dict in metadata_customise_dicts:
            metadata_customise_file.write("""
{}.{}:
  friendly_name: '{}'
            """.format(
                metadata_customise_dict["entity_namespace"],
                metadata_customise_dict["unique_id"],
                metadata_customise_dict["friendly_name"],
            ).strip() + "\n")
            if "icon" in metadata_customise_dict:
                metadata_customise_file.write("  " + """
  icon: '{}'
                """.format(
                    metadata_customise_dict["icon"],
                ).strip() + "\n")
            if "unit_of_measurement" in metadata_customise_dict:
                metadata_customise_file.write("  " + """
  unit_of_measurement: '{}'
                """.format(
                    metadata_customise_dict["unit_of_measurement"],
                ).strip() + "\n")
        print("Build generate script [homeassistant] entity metadata persisted to [{}]".format(metadata_customise_path))

    # Build compensation YAML
    metadata_compensation_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["linked_entity"].str.len() > 0) &
        (metadata_hass_df["compensation_curve"].str.len() > 0)
        ]
    metadata_compensation_dicts = [row.dropna().to_dict() for index, row in metadata_compensation_df.iterrows()]
    metadata_compensation_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/compensation.yaml"))
    with open(metadata_compensation_path, 'w') as metadata_compensation_file:
        metadata_compensation_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
compensation:
        """.strip() + "\n")
        for metadata_compensation_dict in metadata_compensation_dicts:
            metadata_compensation_file.write("  " + """
  #####################################################################################
  {}:
    unique_id: {}
    source: sensor.{}
    precision: 1
    data_points:{}
            """.format(
                metadata_compensation_dict["linked_entity"],
                metadata_compensation_dict["linked_entity"],
                metadata_compensation_dict["unique_id"],
                "\n      - " + metadata_compensation_dict["compensation_curve"].replace("],[", "]\n      - ["),
            ).strip() + "\n")
        metadata_compensation_file.write("  " + """
  #####################################################################################
        """.strip() + "\n")
        print("Build generate script [homeassistant] entity compensation persisted to [{}]".format(
            metadata_compensation_path))

        # Build inputs YAML
        metadata_inputs_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["entity_namespace"] == "input_boolean") &
            (metadata_hass_df["unique_id"].str.len() > 0) &
            (metadata_hass_df["friendly_name"].str.len() > 0) &
            (metadata_hass_df["entity_domain"] == "Routines")
            ]
        metadata_inputs_dicts = [row.dropna().to_dict() for index, row in metadata_inputs_df.iterrows()]
        metadata_inputs_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/inputs.yaml"))
        with open(metadata_inputs_path, 'w') as metadata_inputs_file:
            metadata_inputs_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
input_boolean:
            """.strip() + "\n")
            for metadata_inputs_dict in metadata_inputs_dicts:
                metadata_inputs_file.write("  " + """
  #####################################################################################
  {}:
    name: {}
    initial: off
                """.format(
                    metadata_inputs_dict["unique_id"],
                    metadata_inputs_dict["friendly_name"],
                ).strip() + "\n")
            metadata_inputs_file.write("""
#######################################################################################
                """.strip() + "\n")

    # Build network devices JSON
    metadata_network_devices_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] == "TPLink") &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["connection_ip"].str.len() > 0)] \
        [[
            "name",
            "device_manufacturer",
            "device_model",
            "connection_vlan",
            "connection_ip",
            "connection_mac"
        ]].rename(
        columns={
            "name": "Name",
            "device_manufacturer": "Manufacturer",
            "device_model": "Model",
            "connection_vlan": "VLAN",
            "connection_ip": "IP",
            "connection_mac": "MAC",
        })
    metadata_network_devices_dicts = [row.dropna().to_dict() for index, row in metadata_network_devices_df.iterrows()]
    metadata_network_devices_dicts = sorted(metadata_network_devices_dicts,
                                            key=lambda metadata_network_devices_dict: metadata_network_devices_dict[
                                                'IP'])
    metadata_network_devices_path = abspath(join(DIR_ROOT, "src/main/resources/data/network_devices.json"))
    with open(metadata_network_devices_path, 'w') as metadata_network_devices_file:
        metadata_network_devices_file.write(json.dumps(metadata_network_devices_dicts, indent=2))

    # Build control YAML
    metadata_control_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] == "Tasmota") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["entity_namespace"] != "sensor") &
        (metadata_hass_df["unique_id"].str.len() > 0)
        ]
    metadata_control_dicts = {}
    for _, metadata_hass_row in metadata_control_df.iterrows():
        if metadata_hass_row["entity_namespace"] not in metadata_control_dicts:
            metadata_control_dicts[metadata_hass_row["entity_namespace"]] = {}
        metadata_control_state = "on" if metadata_hass_row["entity_namespace"] == "switch" and \
                                         "tasmota_device_config" in metadata_hass_row and \
                                         "PowerOnState" in json.loads(metadata_hass_row["tasmota_device_config"]) and \
                                         json.loads(metadata_hass_row["tasmota_device_config"])["PowerOnState"] == 1 \
            else "off"
        if metadata_control_state not in metadata_control_dicts[metadata_hass_row["entity_namespace"]]:
            metadata_control_dicts[metadata_hass_row["entity_namespace"]][metadata_control_state] = []
        metadata_control_dicts[metadata_hass_row["entity_namespace"]][metadata_control_state] \
            .append(metadata_hass_row["unique_id"])
    metadata_control_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/control.yaml"))
    with open(metadata_control_path, 'w') as metadata_control_file:
        metadata_control_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
fan:
  - platform: group
    name: Deck Fan
    unique_id: deck_fan
    entities:
      - fan.deck_east_fan
      - fan.deck_west_fan
        """.strip() + "\n")
        metadata_control_file.write("""
#######################################################################################
            """.strip() + "\n")

        # Build HASS integration YAML
        metadata_alias_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["entity_namespace"].str.len() > 0) &
            (metadata_hass_df["unique_id"].str.len() > 0) &
            (metadata_hass_df["entity_namespace"].str.len() > 0) &
            (metadata_hass_df["google_aliases"].str.len() > 0) &
            (metadata_hass_df["device_suggested_area"].str.len() > 0)
            ]
        metadata_alias_dicts = [row.dropna().to_dict() for index, row in metadata_alias_df.iterrows()]
        metadata_alias_path = abspath(join(DIR_ROOT, "src/main/resources/data/hass-entities.yaml"))
        with open(metadata_alias_path, 'w') as metadata_alias_file:
            metadata_alias_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
            for metadata_alias_dict in metadata_alias_dicts:
                metadata_alias_room = metadata_alias_dict["suggested_area_override"] \
                    if "suggested_area_override" in metadata_alias_dict else metadata_alias_dict[
                    "device_suggested_area"]
                metadata_alias_room_name = metadata_alias_dict["suggested_area_override_name"] \
                    if "suggested_area_override_name" in metadata_alias_dict else metadata_alias_dict[
                    "device_suggested_area"]
                metadata_alias_aliases = ["{}{}{}".format(metadata_alias_room_name,
                                                          "" if alias.startswith("s ") else " ", alias)
                                          for alias in metadata_alias_dict["google_aliases"].split(',')]
                metadata_alias_name = metadata_alias_aliases.pop(0)
                metadata_alias_aliases.extend(metadata_alias_dict["google_aliases"].split(','))
                metadata_alias_file.write("""
{}.{}:
  name: {}
  aliases: {}
  room: {}
                    """.format(
                    metadata_alias_dict["entity_namespace"],
                    metadata_alias_dict["unique_id"],
                    metadata_alias_name,
                    metadata_alias_aliases,
                    metadata_alias_room,
                ).strip() + "\n")
            metadata_alias_file.write("""
#######################################################################################
                """.strip() + "\n")

        # Build proxy YAML
        metadata_proxy_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["device_via_device"] == "Proxy") &
            (metadata_hass_df["entity_namespace"] == "sensor") &
            (metadata_hass_df["unique_id"].str.len() > 0) &
            (metadata_hass_df["friendly_name"].str.len() > 0) &
            (metadata_hass_df["linked_entity"].str.len() > 0) &
            (metadata_hass_df["device_class"].str.len() > 0) &
            (metadata_hass_df["device_class"].str.len() > 0) &
            (metadata_hass_df["unit_of_measurement"].str.len() > 0)
            ]
        metadata_proxy_dicts = [row.dropna().to_dict() for index, row in metadata_proxy_df.iterrows()]
        metadata_proxy_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/proxy.yaml"))
        with open(metadata_proxy_path, 'w') as metadata_proxy_file:
            metadata_proxy_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
template:
  #####################################################################################
  - sensor:
            """.strip() + "\n")
            for metadata_proxy_dict in metadata_proxy_dicts:
                metadata_proxy_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: {}
        state_class: {}
        unit_of_measurement: "{}"
        state: '{{{{ states("sensor.{}") | float(None) }}}}'
                    """.format(
                    metadata_proxy_dict["unique_id"].replace("template_", ""),
                    metadata_proxy_dict["device_class"],
                    metadata_proxy_dict["state_class"],
                    metadata_proxy_dict["unit_of_measurement"],
                    metadata_proxy_dict["linked_entity"],
                ).strip() + "\n")
            metadata_proxy_file.write("""
#######################################################################################
                """.strip() + "\n")

    # Build media YAML
    metadata_media_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        ((metadata_hass_df["device_via_device"] == "Google") | (metadata_hass_df["device_via_device"] == "Sonos")) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["connection_ip"].str.len() > 0)
        ]
    metadata_media_google_dicts = [row.dropna().to_dict()
                                   for index, row in
                                   metadata_media_df.query("device_via_device == 'Google'").iterrows()]
    metadata_media_sonos_dicts = [row.dropna().to_dict()
                                  for index, row in metadata_media_df.query("device_via_device == 'Sonos'").iterrows()]
    metadata_media_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/media.yaml"))
    with open(metadata_media_path, 'w') as metadata_media_file:
        metadata_media_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        metadata_media_file.write("""
# NOTE: Use for populating the Google Cast UI integration 'known_hosts' field 
# cast:
#  known_hosts: {}
        """.format(
            ','.join(sorted(map(str, [metadata_media_dict['connection_ip'] for metadata_media_dict in
                                      metadata_media_google_dicts])))
        ).strip() + "\n")
        metadata_media_file.write("""
#######################################################################################


#######################################################################################
# TODO: Disable TV while broken
#wake_on_lan:
#automation:
#  - id: media_lounge_tv_on
#    alias: "Media: Turn on lounge TV"
#    triggers:
#      - trigger: webostv.turn_on
#        entity_id: media_player.lg_webos_tv
#    actions:
#      # wakeonlan -i 10.0.4.255 -p 9 4c:ba:d7:bf:94:d0 works!
#      - action: wake_on_lan.send_magic_packet
#        data:
#          mac: 4c:ba:d7:bf:94:d0
#          broadcast_address: 10.0.4.255
#          broadcast_port: 9
#######################################################################################


#######################################################################################
sonos:
  media_player:
    hosts:
        """.strip() + "\n")
        for metadata_media_sonos_dict in \
                sorted(metadata_media_sonos_dicts,
                       key=lambda metadata_media_sonos_dicts: metadata_media_sonos_dicts['connection_ip']):
            metadata_media_file.write("      " + """
      - {}
            """.format(
                metadata_media_sonos_dict['connection_ip']
            ).strip() + "\n")
        metadata_media_file.write("""      
#######################################################################################
            """.strip() + "\n")

        # Build security YAML
        metadata_lock_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["entity_namespace"] == "lock") &
            (metadata_hass_df["unique_id"].str.len() > 0)
            ]
        metadata_lock_dicts = [row.dropna().to_dict() for index, row in metadata_lock_df.iterrows()]
        metadata_contact_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["device_model"] == "SNZB-04") &
            (metadata_hass_df["unique_id"].str.len() > 0)
            ]
        metadata_contact_dicts = [row.dropna().to_dict() for index, row in metadata_contact_df.iterrows()]
        metadata_locks_all_locked_template = " and ".join([
            "states('lock.{}') == 'locked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_locks_some_locked_template = " or ".join([
            "states('lock.{}') == 'locked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_locks_some_unlocked_template = " or ".join([
            "states('lock.{}') == 'unlocked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_state_all_on_template = " and ".join([
            "states('binary_sensor.template_{}') == 'on'".format(
                metadata_lock_dict["unique_id"].replace("_lock", "_state"))
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_security_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/security.yaml"))
        with open(metadata_security_path, 'w') as metadata_security_file:
            metadata_security_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
stream:
#######################################################################################
input_boolean:
  #####################################################################################
  home_security_triggered:
    name: Security triggered flag
    initial: false
            """.strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  {}:
    name: {} Security
               """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                ).strip() + "\n")
            metadata_security_file.write("""
#######################################################################################
template:
  #####################################################################################
  - binary_sensor:
            """.strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_lock = metadata_lock_dict["unique_id"]
                metadata_contact = "template_" + metadata_lock_dict["unique_id"].replace("_lock",
                                                                                         "_sensor_contact_last")
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        icon: >-
          {{% if states('binary_sensor.{}') == 'off' and states('lock.{}') == 'locked' %}}
            mdi:shield-lock
          {{% else %}}
            mdi:shield-lock-open
          {{% endif %}}
        state: >-
          {{% if states('binary_sensor.{}') == 'off' and states('lock.{}') == 'locked' %}}
            on
          {{% else %}}
            off
          {{% endif %}}
               """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_contact,
                    metadata_lock,
                    metadata_contact,
                    metadata_lock,
                ).strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: door
        state: >-
          {{% if states('binary_sensor.{}') not in ['unavailable', 'unknown', 'none', 'n/a'] %}}
            {{{{ states('binary_sensor.{}') }}}}
          {{% else %}}
            {{{{ states('binary_sensor.{}') }}}}
          {{% endif %}}
                """.format(
                    metadata_contact_dict["unique_id"].replace("template_", ""),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"],
                ).strip() + "\n")
            metadata_security_file.write("  " + """
  #####################################################################################
  - sensor:
            """.strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: battery
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{% if states('sensor.{}') not in ['unavailable', 'unknown', 'none', 'n/a'] %}}
            {{{{ states('sensor.{}') | int(None) }}}}
          {{% else %}}
            {{{{ states('sensor.{}') | int(None) }}}}
          {{% endif %}}
                """.format(
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", ""),
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", "").replace(
                        "_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", "").replace(
                        "_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("contact", "battery"),
                ).strip() + "\n")
            metadata_security_file.write("""
#######################################################################################
automation:
  #####################################################################################
  - id: routine_home_security_check_on
    alias: "Routine: Attempt to put Home into Secure mode at regular intervals"
    mode: queued
    triggers:
      - trigger: time_pattern
        minutes: 15
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('input_boolean.home_security') == 'off' }}}}
        then:
          - action: input_boolean.turn_on
            entity_id: input_boolean.home_security
  #####################################################################################
  - id: routine_home_security_on
    alias: "Routine: Put Home into Secure mode"
    mode: queued
    triggers:
      - trigger: state
        entity_id: input_boolean.home_security
        to: 'on'
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ {} }}}}
        then:
          - action: input_boolean.turn_on
            entity_id: input_boolean.home_security_triggered
          - delay: '00:00:01'
          - action: input_boolean.turn_off
            entity_id: input_boolean.home_security
        else:
          - action: input_boolean.turn_off
            entity_id: input_boolean.home_security_triggered
      - action: input_boolean.turn_on
        entity_id:
            """.format(
                metadata_locks_some_unlocked_template
            ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("          " + """
          - input_boolean.{}                
                """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_home_security_off
    alias: "Routine: Take Home out of Secure mode"
    mode: queued
    triggers:
      - trigger: state
        entity_id: input_boolean.home_security
        to: 'off'
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('input_boolean.home_security_triggered') == 'on' }}}}
        then:
          - action: input_boolean.turn_off
            entity_id: input_boolean.home_security_triggered
        else:
          - action: input_boolean.turn_off
            entity_id:
            """.format(
                metadata_locks_some_locked_template,
            ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("              " + """
              - input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_all_on
    alias: "Routine: {} all on"
    mode: queued
    triggers:
      - trigger: state
        entity_id: binary_sensor.{}
        to: 'on'
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ {} }}}}
        then:
          - action: input_boolean.turn_on
            entity_id: input_boolean.home_security
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_state_all_on_template
                ).strip() + "\n")
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_all_off
    alias: "Routine: {} all off"
    mode: queued
    triggers:
      - trigger: state
        entity_id: binary_sensor.{}
        to: 'off'
    actions:
      - action: input_boolean.turn_on
        entity_id: input_boolean.home_security_triggered
      - action: input_boolean.turn_off
        entity_id: input_boolean.home_security
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_security_on
    alias: "Routine: Put {} into Secure mode"
    mode: queued
    triggers:
      - trigger: state
        entity_id: input_boolean.{}_security
        to: 'on'
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('lock.{}') == 'unlocked' }}}}
        then:
          - delay: '00:00:01'
          - action: input_boolean.turn_off
            entity_id: input_boolean.{}_security
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - action: lock.lock
            entity_id: lock.{}
                """.format(
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_sensor_contact_last"),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_security_off
    alias: "Routine: Take {} out of Secure mode"
    mode: queued
    triggers:
      - trigger: state
        entity_id: input_boolean.{}_security
        to: 'off'
    actions:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('lock.{}') == 'locked' }}}}
        then:
          - action: lock.unlock
            entity_id: lock.{}
                """.format(
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                ).strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_on
    alias: "Routine: {} on"
    mode: queued
    triggers:
      - trigger: state
        entity_id: binary_sensor.{}
        to: 'off'
    actions:
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - action: lock.lock
            entity_id: lock.{}
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - action: lock.lock
            entity_id: lock.{}
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - action: lock.lock
            entity_id: lock.{}
                """.format(
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("_", " ").title(),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last",
                                                                                        "_lock"),
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_on
    alias: "Routine: {} on"
    mode: queued
    triggers:
      - trigger: state
        entity_id: binary_sensor.{}
        to: 'on'
    actions:
      - action: input_boolean.turn_on
        entity_id: input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_off
    alias: "Routine: {} off"
    mode: queued
    triggers:
      - trigger: state
        entity_id: binary_sensor.{}
        to: 'off'
    actions:
      - action: input_boolean.turn_off
        entity_id: input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            metadata_security_file.write("""      
#######################################################################################
                """.strip() + "\n")

    # Build lighting YAML
    metadata_lighting_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        ((metadata_hass_df["device_via_device"] == "Phillips") | (metadata_hass_df["device_via_device"] == "IKEA")) &
        ((metadata_hass_df["entity_namespace"].str.len() > 0) & (metadata_hass_df["entity_namespace"] == "light")) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["friendly_name"].str.len() > 0)
        ]
    metadata_lighting_dicts = [row.dropna().to_dict() for index, row in metadata_lighting_df.iterrows()]
    metadata_lighting_automations_dicts = {}
    for metadata_lighting_dict in metadata_lighting_dicts:
        if "linked_entity" in metadata_lighting_dict:
            if metadata_lighting_dict["linked_entity"] not in metadata_lighting_automations_dicts:
                metadata_lighting_automations_dicts[metadata_lighting_dict["linked_entity"]] = []
            metadata_lighting_automations_dicts[metadata_lighting_dict["linked_entity"]].append(metadata_lighting_dict)
    metadata_lighting_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/lighting.yaml"))
    with open(metadata_lighting_path, 'w') as metadata_lighting_file:
        metadata_lighting_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
adaptive_lighting:
        """.strip() + "\n")
        for automation_name in metadata_lighting_automations_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  - name: {}
    interval: 30
    transition: 20
    min_brightness: {}
    max_brightness: 100
    min_color_temp: {}
    max_color_temp: {}
    only_once: false
    take_over_control: true
    detect_non_ha_changes: true
    lights:
        """.format(
                automation_name.replace("switch.adaptive_lighting_", ""),
                "1" if "dimming" in automation_name else "100",
                "2700" if "narrowband" in automation_name else "2500",
                "4000" if "narrowband" in automation_name else "5500",
            ).strip() + "\n")
            for metadata_lighting_group_dict in metadata_lighting_automations_dicts[automation_name]:
                metadata_lighting_file.write("      " + """
        - light.{}
                  """.format(
                    metadata_lighting_group_dict["unique_id"],
                ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
input_boolean:
  lighting_reset_adaptive_lighting_all:
    name: All
    initial: false
        """.strip() + "\n")
        for metadata_lighting_dict in metadata_lighting_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  lighting_reset_adaptive_lighting_{}:
    name: {}
    initial: false
              """.format(
                metadata_lighting_dict["unique_id"],
                metadata_lighting_dict["friendly_name"],
            ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
automation:
  #####################################################################################
  - id: lighting_reset_adaptive_lighting_announce
    alias: 'Lighting: Reset Adaptive Lighting on bulb announce'
    mode: single
    triggers:
      - trigger: mqtt
        topic: zigbee/bridge/event
    condition:
      - condition: template
        value_template: '{{ trigger.payload_json.data.friendly_name | regex_search(" Bulb 1$") }}'
    actions:
      ################################################################################
      - variables:
          light: '{{ "light." + (trigger.payload_json.data.friendly_name | regex_replace(" Bulb 1$") | replace(" ", "_") | lower) }}'
          light_reset: '{{ "input_boolean.lighting_reset_adaptive_lighting_" + (light | replace("light.", "")) }}'
      ################################################################################
      - if:
          - condition: template
            value_template: '{{ is_state(light_reset, "off") }}'
        then:
          - action: input_boolean.turn_on
            data_template:
              entity_id: '{{ light_reset }}'
        else:
          - action: light.turn_on
            data_template:
              color_temp: 366
              brightness_pct: 100
              entity_id: '{{ light }}'
        """.strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
  - id: lighting_reset_adaptive_lighting_for_all_lights
    alias: 'Lighting: Reset Adaptive Lighting for All Lights'
    mode: single
    triggers:
      - trigger: state
        entity_id: input_boolean.lighting_reset_adaptive_lighting_all
        from: 'off'
        to: 'on'
    actions:
        """.strip() + "\n")
        for automation_name in metadata_lighting_automations_dicts:
            metadata_lighting_file.write("      " + """
      - action: switch.turn_off
        entity_id: {}
      - delay: '00:00:01'
      - action: switch.turn_on
        entity_id: {}
            """.format(
                automation_name,
                automation_name,
            ).strip() + "\n")
        metadata_lighting_file.write("      " + """
      - action: input_boolean.turn_off
        entity_id: input_boolean.lighting_reset_adaptive_lighting_all
        """.strip() + "\n")
        for metadata_lighting_dict in metadata_lighting_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  - id: lighting_reset_adaptive_lighting_{}
    alias: "Lighting: Reset Adaptive Lighting on request of {}"
    triggers:
      - trigger: state
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
        from: 'off'
        to: 'on'
            """.format(
                metadata_lighting_dict["unique_id"],
                metadata_lighting_dict["friendly_name"],
                metadata_lighting_dict["unique_id"],
            ).strip() + "\n")
            reset_double_trigger_timeout = "'00:00:10'"
            if "linked_entity" in metadata_lighting_dict:
                metadata_lighting_file.write("    " + """
    actions:
      - action: adaptive_lighting.set_manual_control
        data:
          entity_id: {}
          lights: light.{}
          manual_control: false
      - delay: {}
      - action: input_boolean.turn_off
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
                """.format(
                    metadata_lighting_dict["linked_entity"],
                    metadata_lighting_dict["unique_id"],
                    reset_double_trigger_timeout,
                    metadata_lighting_dict["unique_id"],
                ).strip() + "\n")
            else:
                device_config = json.loads(metadata_lighting_dict["zigbee_device_config"]) \
                    if "zigbee_device_config" in metadata_lighting_dict else {}
                metadata_lighting_file.write("    " + """
    actions:
      - action: light.turn_on
        data_template:
          color_temp: {}
          brightness_pct: {}
          entity_id: light.{}
      - delay: {}
      - action: input_boolean.turn_off
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
                """.format(
                    device_config["color_temp_startup"] if "color_temp_startup" in device_config else 366,
                    int(device_config[
                            "hue_power_on_brightness"] / 254 * 100) if "hue_power_on_brightness" in device_config else 100,
                    metadata_lighting_dict["unique_id"],
                    reset_double_trigger_timeout,
                    metadata_lighting_dict["unique_id"],
                ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
        """.strip() + "\n")
    print("Build generate script [homeassistant] entity lighting persisted to [{}]".format(metadata_lighting_path))

    # Diagnostics YAML
    metadata_diagnostic_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["entity_domain"] == "Zigbee Link Quality") &
        (metadata_hass_df["entity_group"] == "Diagnostics")
        ]
    metadata_diagnostic_dicts = [row.dropna().to_dict() for index, row in metadata_diagnostic_df.iterrows()]
    metadata_diagnostic_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/diagnostics.yaml"))
    with open(metadata_diagnostic_path, 'w') as metadata_diagnostic_file:
        metadata_diagnostic_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
compensation:
  #####################################################################################
  weatherstation_console_battery_percent:
    unique_id: weatherstation_console_battery_percent
    source: sensor.weatherstation_console_battery_voltage
    unit_of_measurement: "%"
    degree: 3
    precision: 0
    lower_limit: true
    upper_limit: true
    data_points:
      - [ 4, 100 ]
      - [ 3.97, 99 ]
      - [ 3.95, 98 ]
      - [ 3.92, 96 ]
      - [ 3.91, 94 ]
      - [ 3.9, 93 ]
      - [ 3.89, 91 ]
      - [ 3.88, 88 ]
      - [ 3.87, 87 ]
      - [ 3.85, 83 ]
      - [ 3.83, 81 ]
      - [ 3.81, 65 ]
      - [ 3.79, 59 ]
      - [ 3.78, 56 ]
      - [ 3.76, 50 ]
      - [ 3.75, 49 ]
      - [ 3.74, 43 ]
      - [ 3.72, 38 ]
      - [ 3.7, 35 ]
      - [ 3.68, 33 ]
      - [ 3.66, 28 ]
      - [ 3.64, 22 ]
      - [ 3.62, 21 ]
      - [ 3.61, 18 ]
      - [ 3.59, 16 ]
      - [ 3.58, 15 ]
      - [ 3.56, 10 ]
      - [ 3.54, 9 ]
      - [ 3.52, 8 ]
      - [ 3.49, 7 ]
      - [ 3.48, 6 ]
      - [ 3.46, 5 ]
      - [ 3.44, 3 ]
      - [ 3.4, 2 ]
      - [ 3.38, 1 ]
      - [ 3.32, 0 ]
#######################################################################################
template:
  #####################################################################################
  - sensor:
      #################################################################################
      - unique_id: weatherstation_console_battery_percent_int
        device_class: battery
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{ states('sensor.compensation_sensor_weatherstation_console_battery_voltage') | int(None) }}
      #################################################################################
      - unique_id: weatherstation_coms_signal_quality_percentage
        device_class: signal_strength
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{ states('sensor.weatherstation_coms_signal_quality') | int(0) }}
        """.strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: signal_strength
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{{{ min(states('sensor.{}') | float(0) / 100 * 100, 100) | int(0) }}}}
              """.format(
                metadata_diagnostic_dict["unique_id"].replace("template_", ""),
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("_percentage", ""),
            ).strip() + "\n")
        metadata_diagnostic_file.write("""
#######################################################################################
input_boolean:
  #####################################################################################
  network_refresh_zigbee_router_lqi:
    name: Refresh state
    initial: false
#######################################################################################
automation:
  #####################################################################################
  - id: network_refresh_zigbee_router_lqi_action_scheduled
    alias: "Network: Refresh Zigbee router network link qualities on schedule"
    triggers:
      - trigger: time_pattern
        hours: 1
    actions:
      - action: input_boolean.turn_on
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
  #####################################################################################
  - id: network_refresh_zigbee_router_lqi_action
    alias: "Network: Refresh Zigbee router network link qualities"
    triggers:
      - trigger: state
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
        from: 'off'
        to: 'on'
    actions:
        """.strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      - action: mqtt.publish
        data:
          topic: "zigbee/{}/{}/set"
          payload: '{{"read":{{"attributes":["dateCode","modelId"],"cluster":"genBasic","options":{{}}}}}}'
      - delay: '00:00:01'
            """.format(
                metadata_diagnostic_dict["friendly_name"],
                "11" if "outlet" in metadata_diagnostic_dict["unique_id"] else "1",
            ).strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ ((states('sensor.{}') | lower) in ['unavailable', 'unknown', 'none', 'n/a']) or
                    ((as_timestamp(now()) - as_timestamp(states('sensor.{}'))) > {}) }}}}
        then:
          - action: mqtt.publish
            data:
              topic: "zigbee/{}"
              payload: '{{ "last_seen": null, "linkquality": 0, "state": null, "update": {{ "installed_version": null, "latest_version": null, "state": null }}, "update_available": false }}'
            """.format(
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("linkquality_percentage",
                                                                                       "last_seen"),
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("linkquality_percentage",
                                                                                       "last_seen"),
                len(metadata_diagnostic_dicts) + 5,
                metadata_diagnostic_dict["friendly_name"],
            ).strip() + "\n")
        metadata_diagnostic_file.write("      " + """
      - action: input_boolean.turn_off
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
#######################################################################################
        """.strip() + "\n")

        # Electricity YAML
        metadata_electricity_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["device_via_device"] == "Powercalc Proxy") &
            (metadata_hass_df["entity_namespace"].str.len() > 0) &
            (metadata_hass_df["unique_id"].str.len() > 0) &
            (metadata_hass_df["powercalc_enable"] == "True")
            ]
        metadata_electricity_proxy_dicts = [row.to_dict() for index, row in metadata_electricity_df.iterrows()]
        metadata_electricity_df = metadata_hass_df[
            (metadata_hass_df["index"] > 0) &
            (metadata_hass_df["entity_status"] == "Enabled") &
            (metadata_hass_df["entity_namespace"].str.len() > 0) &
            (metadata_hass_df["unique_id"].str.len() > 0) &
            (metadata_hass_df["powercalc_enable"] == "True")
            ]
        metadata_electricity_dicts = {}
        metadata_electricity_ungrouped_dicts = []
        metadata_electricity_single_group_dicts = {}
        for dict in [row.dropna().to_dict() for index, row in metadata_electricity_df.iterrows()]:
            if "powercalc_group_4" in dict:
                dict_group4 = dict["powercalc_group_4"]
                if "powercalc_group_1" in dict and "powercalc_group_2" in dict and "powercalc_group_3" in dict:
                    dict_group1 = dict["powercalc_group_1"]
                    dict_group2 = dict["powercalc_group_2"]
                    dict_group3 = dict["powercalc_group_3"]
                    if dict_group1 not in metadata_electricity_dicts:
                        metadata_electricity_dicts[dict_group1] = {}
                    if dict_group2 not in metadata_electricity_dicts[dict_group1]:
                        metadata_electricity_dicts[dict_group1][dict_group2] = {}
                    if dict_group3 not in metadata_electricity_dicts[dict_group1][dict_group2]:
                        metadata_electricity_dicts[dict_group1][dict_group2][dict_group3] = {}
                    if dict_group4 not in metadata_electricity_dicts[dict_group1][dict_group2][dict_group3]:
                        metadata_electricity_dicts[dict_group1][dict_group2][dict_group3][dict_group4] = []
                    metadata_electricity_dicts[dict_group1][dict_group2][dict_group3][dict_group4].append(dict)
                else:
                    if dict_group4 not in metadata_electricity_single_group_dicts:
                        metadata_electricity_single_group_dicts[dict_group4] = []
                    metadata_electricity_single_group_dicts[dict_group4].append(dict)
            else:
                metadata_electricity_ungrouped_dicts.append(dict)
        metadata_electricity_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/electricity.yaml"))
        with open(metadata_electricity_path, 'w') as metadata_electricity_file:
            metadata_electricity_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
powercalc:
  force_update_frequency: 00:00:05
  enable_autodiscovery: false
  power_sensor_precision: 1
  energy_sensor_precision: 3
  power_sensor_naming: '{} Power'
  energy_sensor_naming: '{} Energy'
  create_utility_meters: true
  utility_meter_types:
    - daily
    - weekly
    - monthly
    - yearly
  #####################################################################################
  sensors:
            """.strip() + "\n")
            for dict in metadata_electricity_ungrouped_dicts:
                dict_config = \
                    ("\n      " + dict["powercalc_config"].replace("\n", "\n      ")) \
                        if "powercalc_config" in dict else ""
                metadata_electricity_file.write("    " + """
    ###################################################################################
    - entity_id: {}.{}{}
                """.format(
                    dict["entity_namespace"],
                    dict["unique_id"],
                    dict_config,
                ).strip() + "\n")
            for dict_group1 in metadata_electricity_single_group_dicts:
                dict_config = \
                    ("\n        " + dict["powercalc_config"].replace("\n", "\n        ")) \
                        if "powercalc_config" in dict else ""
                metadata_electricity_file.write("    " + """
    ###################################################################################
    - create_group: {}
      entities:
                """.format(
                    dict_group1,
                ).strip() + "\n")
                for dict in metadata_electricity_single_group_dicts[dict_group1]:
                    dict_config = \
                        ("\n          " + dict["powercalc_config"].replace("\n", "\n          ")) \
                            if "powercalc_config" in dict else ""
                    metadata_electricity_file.write("        " + """
        - entity_id: {}.{}{}
                    """.format(
                        dict["entity_namespace"],
                        dict["unique_id"],
                        dict_config,
                    ).strip() + "\n")
            for dict_group1 in metadata_electricity_dicts:
                metadata_electricity_file.write("    " + """
    ###################################################################################
    - create_group: {}
      entities:
                """.format(
                    dict_group1
                ).strip() + "\n")
                for dict_group2 in metadata_electricity_dicts[dict_group1]:
                    metadata_electricity_file.write("        " + """
        ###############################################################################
        - create_group: {}
          entities:
                    """.format(
                        dict_group2
                    ).strip() + "\n")
                    for dict_group3 in metadata_electricity_dicts[dict_group1][dict_group2]:
                        metadata_electricity_file.write("            " + """
            ###########################################################################
            - create_group: {}
              entities:
                        """.format(
                            dict_group3
                        ).strip() + "\n")
                        for dict_group4 in metadata_electricity_dicts[dict_group1][dict_group2][dict_group3]:
                            metadata_electricity_file.write("                " + """
                #######################################################################
                - create_group: {}
                  entities:
                            """.format(
                                dict_group4,
                            ).strip() + "\n")
                            for dict in metadata_electricity_dicts[dict_group1][dict_group2][dict_group3][dict_group4]:
                                dict_config = \
                                    ("\n                      " + dict["powercalc_config"].replace("\n",
                                                                                                   "\n                      ")) \
                                        if "powercalc_config" in dict else ""
                                metadata_electricity_file.write("                    " + """
                    - entity_id: {}.{}{}{}
                              """.format(
                                    dict["entity_namespace"],
                                    dict["unique_id"],
                                    dict_config,
                                    "\n                      manufacturer: {}\n".format(
                                        dict["manufacturer_alias"]) if "manufacturer_alias" in dict else "",
                                ).strip() + "\n")
            metadata_electricity_file.write("  " + """
  #####################################################################################
            """.strip() + "\n")
            metadata_electricity_file.write("""
template:
  #####################################################################################
  - binary_sensor:
            """.strip() + "\n")
            for metadata_electricity_proxy_dict in metadata_electricity_proxy_dicts:
                metadata_electricity_proxy_type = metadata_electricity_proxy_dict["device_proxy_type"] \
                    if (
                        "device_proxy_type" in metadata_electricity_proxy_dict and
                        str(metadata_electricity_proxy_dict["device_proxy_type"]) != "" and
                        str(metadata_electricity_proxy_dict["device_proxy_type"]) != "nan" and
                        str(metadata_electricity_proxy_dict["device_proxy_type"]) != "none"
                ) else "switch"
                metadata_electricity_proxy_state = "states('media_player.{}') != \"unavailable\"".format(
                    metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                ) if (metadata_electricity_proxy_type == "media_player" and
                      "device_model" in metadata_electricity_proxy_dict and metadata_electricity_proxy_dict[
                          "device_model"] == "Move"
                      ) else (
                    "states('{}.{}')".format(
                        metadata_electricity_proxy_type,
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                    ))
                metadata_electricity_file.write("      " + """
      #################################################################################
      - unique_id: {}
        state: >-
          {{{{ {} }}}}
                """.format(
                    metadata_electricity_proxy_dict["unique_id"].replace("template_", ""),
                    metadata_electricity_proxy_state,
                ).strip() + "\n")
                if "device_model" in metadata_electricity_proxy_dict and metadata_electricity_proxy_dict[
                    "device_model"] == "STARKVIND":
                    metadata_electricity_file.write("        " + """
        attributes:
          fan_speed: >-
            {{{{ states('sensor.{}_fan_speed') | int(0) }}}}
                    """.format(
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                    ).strip() + "\n")
                if "device_model" in metadata_electricity_proxy_dict and metadata_electricity_proxy_dict[
                    "device_model"] == "Move":
                    metadata_electricity_file.write("        " + """
        attributes:
          charging_state: >-
            {{%- if states('binary_sensor.{}_power') == "on" and states('sensor.{}_battery') | int(0) < 100 -%}}
              {{{{ 100 - (states('sensor.{}_battery') | int(0)) }}}}
            {{% else %}}
              {{{{ 0 }}}}
            {{% endif %}}
                    """.format(
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                        metadata_electricity_proxy_dict["unique_id"].replace("template_", "").replace("_proxy", ""),
                    ).strip() + "\n")
            metadata_electricity_file.write("      " + """
      #################################################################################
            """.strip() + "\n")

    # Build action YAML
    metadata_action_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["device_via_device"] == "Action") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["friendly_name"].str.len() > 0) &
        (metadata_hass_df["linked_entity"].str.len() > 0) &
        (metadata_hass_df["linked_service"].str.len() > 0) &
        (metadata_hass_df["icon"].str.len() > 0)
        ]
    metadata_action_dicts = [row.dropna().to_dict() for index, row in metadata_action_df.iterrows()]
    metadata_action_path = abspath(join(DIR_ROOT, "src/main/resources/data/custom_packages/scripts.yaml"))
    with open(metadata_action_path, 'w') as metadata_action_file:
        metadata_action_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
script:
        """.strip() + "\n")
        for metadata_action_dict in metadata_action_dicts:
            metadata_action_file.write("  " + """
  #####################################################################################
  {}:
    alias: "{}"
    description: "{}"
    icon: {}
    mode: queued
    sequence:
      - action: {}
        target:
          entity_id: {}
              """.format(
                metadata_action_dict["unique_id"],
                metadata_action_dict["friendly_name"],
                metadata_action_dict["friendly_name"],
                metadata_action_dict["icon"],
                metadata_action_dict["linked_service"],
                metadata_action_dict["linked_entity"],
            ).strip() + "\n")

    # Build lovelace YAML
    metadata_lovelace_df = metadata_hass_df[
        (metadata_hass_df["index"] > 0) &
        (metadata_hass_df["entity_status"] == "Enabled") &
        (metadata_hass_df["entity_namespace"].str.len() > 0) &
        (metadata_hass_df["unique_id"].str.len() > 0) &
        (metadata_hass_df["friendly_name"].str.len() > 0) &
        (metadata_hass_df["entity_domain"].str.len() > 0) &
        (metadata_hass_df["entity_group"].str.len() > 0) &
        (metadata_hass_df["hass_display_mode"].str.len() > 0)
        ]
    metadata_lovelace_dicts = [row.dropna().to_dict() for index, row in metadata_lovelace_df.iterrows()]
    metadata_lovelace_group_domain_dicts = OrderedDict()
    for metadata_lovelace_dict in metadata_lovelace_dicts:
        group = metadata_lovelace_dict["entity_group"]
        domain = metadata_lovelace_dict["entity_domain"]
        if group not in metadata_lovelace_group_domain_dicts:
            metadata_lovelace_group_domain_dicts[group] = OrderedDict()
        if domain not in metadata_lovelace_group_domain_dicts[group]:
            metadata_lovelace_group_domain_dicts[group][domain] = []
        metadata_lovelace_group_domain_dicts[group][domain].append(metadata_lovelace_dict)
    for group in metadata_lovelace_group_domain_dicts:
        metadata_lovelace_path = abspath(join(DIR_ROOT, "src/main/resources/data/ui-lovelace", group.lower() + ".yaml"))
        with open(metadata_lovelace_path, 'w') as metadata_lovelace_file:
            metadata_lovelace_file.write("""
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!            
            """.strip() + "\n")
            for domain in metadata_lovelace_group_domain_dicts[group]:
                metadata_lovelace_graph_dicts = []
                for metadata_lovelace_dict in metadata_lovelace_group_domain_dicts[group][domain]:
                    if metadata_lovelace_dict["hass_display_mode"] == "Graph":
                        metadata_lovelace_graph_dicts.append(metadata_lovelace_dict)
                if metadata_lovelace_graph_dicts:
                    metadata_lovelace_file.write("""
################################################################################
- type: custom:mini-graph-card
  name: {}{}
  font_size_header: 19
  aggregate_func: max
  hours_to_show: 48
  points_per_hour: 6
  line_width: 2
  tap_action: none
  show_state: true
  show_indicator: true
  show:
    extrema: true
    fill: false
  entities:
                    """.format(
                        domain,
                        ("\n  icon: " + metadata_lovelace_graph_dicts[0]["icon"]) if "icon" in
                                                                                     metadata_lovelace_graph_dicts[
                                                                                         0] else ""
                    ).strip() + "\n")
                    for metadata_lovelace_graph_dict in metadata_lovelace_graph_dicts:
                        metadata_lovelace_file.write("    " + ("""
    - entity: {}.{}
      name: {}
                        """.format(
                            metadata_lovelace_graph_dict["entity_namespace"],
                            metadata_lovelace_graph_dict["unique_id"],
                            metadata_lovelace_graph_dict["friendly_name"],
                        )).strip() + "\n")
                if metadata_lovelace_group_domain_dicts[group][domain]:
                    metadata_lovelace_first_display_mode = None
                    for metadata_lovelace_dict in metadata_lovelace_group_domain_dicts[group][domain]:
                        metadata_lovelace_current_display_mode = metadata_lovelace_dict["hass_display_mode"].split("_")[
                            0]
                        if metadata_lovelace_current_display_mode != metadata_lovelace_first_display_mode:
                            metadata_lovelace_first_display_mode = metadata_lovelace_current_display_mode
                            metadata_lovelace_first_dict = metadata_lovelace_dict
                            metadata_lovelace_first_display_type = metadata_lovelace_first_dict["hass_display_type"] \
                                if "hass_display_type" in metadata_lovelace_first_dict else "entities"
                            if metadata_lovelace_first_display_type == "entities":
                                metadata_lovelace_file.write("""
################################################################################
- type: entities
                                """.strip() + "\n")
                                if not metadata_lovelace_graph_dicts:
                                    metadata_lovelace_file.write("  " + """
  title: {}
                                    """.format(
                                        domain
                                    ).strip() + "\n")
                                    if "NoToggle" in metadata_lovelace_first_dict["hass_display_mode"]:
                                        metadata_lovelace_file.write("  " + """
  show_header_toggle: false
                                        """.format(
                                            domain
                                        ).strip() + "\n")
                                metadata_lovelace_file.write("  " + """
  entities:
                                """.strip() + "\n")
                        if "hass_display_type" not in metadata_lovelace_dict or metadata_lovelace_dict[
                            "hass_display_type"] == "entities":
                            metadata_lovelace_file.write("    " + ("""
    - entity: {}.{}
      name: {}
                            """.format(
                                metadata_lovelace_dict["entity_namespace"],
                                metadata_lovelace_dict["unique_id"],
                                metadata_lovelace_dict["friendly_name"],
                            )).strip() + "\n")
                            if "icon" in metadata_lovelace_dict:
                                metadata_lovelace_file.write("      " + """
      icon: {}
                                """.format(
                                    metadata_lovelace_dict["icon"],
                                ).strip() + "\n")
                        elif metadata_lovelace_dict["hass_display_mode"] != "Break":
                            metadata_lovelace_file.write("""
################################################################################
- type: {}
  entity: {}.{}
                            """.format(
                                metadata_lovelace_first_display_type,
                                metadata_lovelace_dict["entity_namespace"],
                                metadata_lovelace_dict["unique_id"],
                            ).strip() + "\n")
                            if metadata_lovelace_first_display_type == "picture-entity":
                                metadata_lovelace_file.write("  " + """
  show_name: false
  show_state: false
  camera_view: live
                                """.strip() + "\n")
                        else:
                            metadata_lovelace_file.write("""
################################################################################
- type: {}
                            """.format(
                                metadata_lovelace_first_display_type,
                            ).strip() + "\n")
            metadata_lovelace_file.write("""
################################################################################
            """.strip() + "\n")
            print("Build generate script [homeassistant] entity group [{}] persisted to lovelace [{}]"
                  .format(group.lower(), metadata_lovelace_path))
