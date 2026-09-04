import glob
import os
import stat
import sys
from os.path import *

from pathlib2 import Path

BACKUP_TIMEOUT_HOURS_DEFAULT = "3"
BACKUP_KEEP_DAILY_DEFAULT = "7"
BACKUP_KEEP_WEEKLY_DEFAULT = "4"
BACKUP_KEEP_MONTHLY_DEFAULT = "12"

BACKUP_CONTRACT = """# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, renames the temporary file on success, prunes and sets the exit code. Define
# backup_written below, naming the backup with backup_target (or letting backup_files do both) and
# writing "${BACKUP_TARGET_PATH}.tmp". A snippet leaving the estate changed while it works, such as
# one stopping its own container, also defines backup_interrupted, called on INT, TERM or HUP but
# never on a backup that merely fails. Never assign a wrapper variable, prefix this snippet's own
# state with the module name, and expand a value read from .env as "${VAR:?}", so a missing key
# fails by name rather than corrupting the backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself"""


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

SERVICE_WAIT_ALIVE_SECONDS=900
SERVICE_WAIT_EXECUTING_SECONDS=900

wait_service() {{
  local script="$1" label="$2" interval="$3" timeout="$4" waited=0 ticked=0
  ((interval > 0)) || interval=1
  printf 'Waiting for service to %s ...' "${{label}}"
  while ! "${{ASYSTEM_HOME}}/${{script}}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      printf ' failed\\n'
      echo "ERROR: Service failed to ${{label}} within [${{timeout}}] seconds" >&2
      exit 1
    fi
    for ((ticked = 0; ticked < interval; ticked++)); do
      sleep 1
      printf '.'
    done
    waited=$((waited + interval))
  done
  printf ' done\\n'
}}

wait_service "checkalive.sh" "come alive" 1 "${{SERVICE_WAIT_ALIVE_SECONDS}}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

{}

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

wait_service "checkexecuting.sh" "start executing" 1 "${{SERVICE_WAIT_EXECUTING_SECONDS}}"
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


def write_container_volumes(module_name=None, working_dir=None):
    root_dir = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(root_dir)
    if working_dir is None:
        working_dir = join(root_dir, "src/main/resources")
    script_path = join(working_dir, "volumes.sh")
    if not isdir(dirname(script_path)):
        os.makedirs(dirname(script_path), exist_ok=True)
    _verify_container_partlabels(root_dir, module_name)
    with open(script_path, 'w') as script_file:
        script_file.write(r"""
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
        """.strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(module_name, script_path))


def _verify_container_partlabels(root_dir, module_name):
    declared = {}
    for fstab_path in sorted(glob.glob(join(root_dir, "../../*/_*/src/main/resources/fstab"))):
        host = basename(dirname(dirname(dirname(dirname(fstab_path)))))
        for line in Path(fstab_path).read_text().splitlines():
            fields = line.split()
            if len(fields) < 2 or line.lstrip().startswith("#") or not fields[0].startswith("PARTLABEL="):
                continue
            declared.setdefault(fields[0][len("PARTLABEL="):], []).append("{} {}".format(host, fields[1]))
    for label, claims in sorted(declared.items()):
        if len(claims) > 1:
            print("Build generate script [{}] partlabel [{}] is claimed by [{}], "
                  "a disk moved between hosts would mount against the wrong declaration"
                  .format(module_name, label, ", ".join(claims)))


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
        Path(script_source_path).write_text(BACKUP_CONTRACT + """

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
    if not script_source.startswith(BACKUP_CONTRACT):
        raise ValueError("Snippet contract violated in [{}], its leading comment block must match "
                         "BACKUP_CONTRACT verbatim".format(script_source_path))
    script_path = abspath(join(working_dir, "backup.sh"))
    with open(script_path, 'w') as script_file:
        script_file.write("""
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# shellcheck disable=SC1090,SC2034,SC2329

set -o pipefail

# Usage:
#
#   ./backup.sh              take a backup, full or delta off an eligible parent
#   ./backup.sh --prune      drop local runs older than BACKUP_RETAIN_DAYS, never the newest
#   ./backup.sh --prune-gfs  apply the grandfather-father-son window
#
#   BACKUP_SKIP_HOURS=0 ./backup.sh            take a backup now, whatever the throttle says
#   BACKUP_RETAIN_DAYS=0 ./backup.sh --prune   keep only the newest local run
#
# Both prune forms take the backup root as an optional argument, defaulting to the module's own.
# Any variable below can be set on the command line, unless the module's .env already sets it.
#
# BACKUP_SOURCE_PATH      the data path backed up, defaulting to this module's own
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_KEEP_DAILY       the daily backups kept by --prune-gfs
# BACKUP_KEEP_WEEKLY      the weekly backups kept by --prune-gfs
# BACKUP_KEEP_MONTHLY     the monthly backups kept by --prune-gfs
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_TIMEOUT_HOURS    the budget a backup waiting on its service allows before abandoning the run

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
BACKUP_KEEP_DAILY="${{BACKUP_KEEP_DAILY:-{keep_daily}}}"
BACKUP_KEEP_WEEKLY="${{BACKUP_KEEP_WEEKLY:-{keep_weekly}}}"
BACKUP_KEEP_MONTHLY="${{BACKUP_KEEP_MONTHLY:-{keep_monthly}}}"
BACKUP_SKIP_HOURS="${{BACKUP_SKIP_HOURS:-1}}"
BACKUP_SERVICE_RESTART="${{BACKUP_SERVICE_RESTART:-true}}"
BACKUP_TIMEOUT_HOURS="${{BACKUP_TIMEOUT_HOURS:-{timeout}}}"
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

backup_dir_is_full() {{
  local dir="${{1}}" stamp="${{2}}" path
  for path in "${{dir}}/${{stamp}}"/*; do
    backup_is_full "$(basename "${{path}}")" && return 0
  done
  return 1
}}

backup_pruned_gfs() {{
  local dir="${{1:-${{BACKUP_INTERNAL_ROOT_DIR}}}}" names name stamp bucket
  mapfile -t names < <(backup_listed "${{dir}}")
  [ "${{#names[@]}}" -gt 1 ] || return 0
  declare -A keep=() day_seen=()
  local count="${{#names[@]}}" index day chain
  for ((index = count - 1; index >= 0; index--)); do
    day="${{names[${{index}}]:0:10}}"
    if [ -z "${{day_seen[${{day}}]:-}}" ]; then
      [ "${{#day_seen[@]}}" -ge "${{BACKUP_KEEP_DAILY}}" ] && break
      day_seen["${{day}}"]=1
    fi
    keep["${{names[${{index}}]}}"]=daily
  done
  declare -A week_seen=() month_seen=()
  for ((index = count - 1; index >= 0; index--)); do
    name="${{names[${{index}}]}}"
    stamp="${{name:0:10}}"
    backup_dir_is_full "${{dir}}" "${{name}}" || continue
    bucket="$(date -d "${{stamp}}" +%G-%V 2>/dev/null)"
    if [ -n "${{bucket}}" ] && [ -z "${{week_seen[${{bucket}}]:-}}" ] && [ "${{#week_seen[@]}}" -lt "${{BACKUP_KEEP_WEEKLY}}" ]; then
      week_seen["${{bucket}}"]=1
      keep["${{name}}"]=weekly
    fi
    bucket="${{stamp:0:7}}"
    if [ -z "${{month_seen[${{bucket}}]:-}}" ] && [ "${{#month_seen[@]}}" -lt "${{BACKUP_KEEP_MONTHLY}}" ]; then
      month_seen["${{bucket}}"]=1
      keep["${{name}}"]=monthly
    fi
  done
  for ((index = count - 1; index >= 0; index--)); do
    name="${{names[${{index}}]}}"
    [ -n "${{keep[${{name}}]:-}}" ] || continue
    backup_dir_is_full "${{dir}}" "${{name}}" && continue
    for ((chain = index - 1; chain >= 0; chain--)); do
      keep["${{names[${{chain}}]}}"]="${{keep[${{names[${{chain}}]}}]:-chain}}"
      backup_dir_is_full "${{dir}}" "${{names[${{chain}}]}}" && break
    done
  done
  for name in "${{names[@]}}"; do
    if [ -z "${{keep[${{name}}]:-}}" ]; then
      rm -rf "${{dir:?}}/${{name}}"
      echo "Pruned backup [${{name}}] outside the grandfather-father-son window"
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

backup_interrupted() {{
  :
}}

{source}

[ "${{BASH_SOURCE[0]}}" = "${{0}}" ] || return 0

if [ "${{1:-}}" = "--prune" ]; then
  backup_pruned "${{2}}"
  exit 0
fi

if [ "${{1:-}}" = "--prune-gfs" ]; then
  backup_pruned_gfs "${{2}}"
  exit 0
fi

find "${{BACKUP_INTERNAL_ROOT_DIR}}" -type f -name '*.tmp' -delete 2>/dev/null

mapfile -t BACKUP_INTERNAL_EXISTING < <(backup_listed)
if [ "${{#BACKUP_INTERNAL_EXISTING[@]}}" -gt 0 ]; then
  BACKUP_INTERNAL_NEWEST="${{BACKUP_INTERNAL_EXISTING[-1]}}"
  BACKUP_INTERNAL_NEWEST_VERSION="$(backup_versioned "${{BACKUP_INTERNAL_NEWEST}}")"
  BACKUP_INTERNAL_AGE=$(($(date +%s) - $(backup_epoch "${{BACKUP_INTERNAL_NEWEST}}")))
  if [ "${{BACKUP_INTERNAL_AGE}}" -lt $((BACKUP_SKIP_HOURS * 3600)) ]; then
    echo "Backup skipped, newest backup [${{BACKUP_INTERNAL_NEWEST}}] of version [${{BACKUP_INTERNAL_NEWEST_VERSION}}] is [${{BACKUP_INTERNAL_AGE}}] seconds old, skipping given within [${{BACKUP_SKIP_HOURS}}] hours"
    exit 0
  fi
fi

echo "Starting backup from version [${{BACKUP_SOURCE_VERSION}}] holding [${{#BACKUP_INTERNAL_EXISTING[@]}}] backups, newest [${{BACKUP_INTERNAL_NEWEST:-none}}] retaining [${{BACKUP_RETAIN_DAYS}}] days, skipping backup if executing again within [${{BACKUP_SKIP_HOURS}}] hours"

trap backup_discarded EXIT
trap 'backup_interrupted; exit 130' INT
trap 'backup_interrupted; exit 143' TERM
trap 'backup_interrupted; exit 129' HUP
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
""".format(module=module_name, source=script_source, timeout=BACKUP_TIMEOUT_HOURS_DEFAULT,
           keep_daily=BACKUP_KEEP_DAILY_DEFAULT, keep_weekly=BACKUP_KEEP_WEEKLY_DEFAULT,
           keep_monthly=BACKUP_KEEP_MONTHLY_DEFAULT).strip())
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
    print("Build generate script [{}] script persisted to [{}]"
          .format(basename(root_dir), script_path))
