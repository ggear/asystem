#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

set -ex

################################################################################
# Update
################################################################################
cd /tmp
dnf-3 makecache --quiet

################################################################################
# Packages
################################################################################
dnf-3 install --quiet -y 'jq-1.7.1'
dnf-3 install --quiet -y 'yq-4.43.1'
dnf-3 install --quiet -y 'nvme-cli-2.15'
dnf-3 install --quiet -y 'acl-2.3.2'
dnf-3 install --quiet -y 'parted-3.6'
dnf-3 install --quiet -y 'util-linux-2.40.4'
dnf-3 install --quiet -y 'usbutils-018'
dnf-3 install --quiet -y 'smartmontools-7.5'
dnf-3 install --quiet -y 'htop-3.4.1'
dnf-3 install --quiet -y 'iotop-c-1.30'
dnf-3 install --quiet -y 'ethtool-6.15'
dnf-3 install --quiet -y 'lm_sensors-3.6.0'
dnf-3 install --quiet -y 'efivar-39'
dnf-3 install --quiet -y 'cifs-utils-7.2'
dnf-3 install --quiet -y 'samba-4.22.4'
dnf-3 install --quiet -y 'samba-client-4.22.4'
dnf-3 install --quiet -y 'cups-2.4.12'
dnf-3 install --quiet -y 'avahi-0.9~rc2'
dnf-3 install --quiet -y 'inotify-tools-4.23.9.0'
dnf-3 install --quiet -y 'powertop-2.15'
dnf-3 install --quiet -y 'python3-3.13.7'
dnf-3 install --quiet -y 'python3-pip-24.3.1'
dnf-3 install --quiet -y 'vim-enhanced-9.1.1723'
dnf-3 install --quiet -y 'nano-8.3'
dnf-3 install --quiet -y 'screen-5.0.1'
dnf-3 install --quiet -y 'tmux-3.5a'
dnf-3 install --quiet -y 'curl-8.11.1'
dnf-3 install --quiet -y 'wget2-wget-2.2.0'
dnf-3 install --quiet -y 'unrar-7.1.7'
dnf-3 install --quiet -y 'rsync-3.4.1'
dnf-3 install --quiet -y 'mediainfo-25.04'
dnf-3 install --quiet -y 'tesseract-5.5.0'
dnf-3 install --quiet -y 'exfatprogs-1.2.9'
dnf-3 install --quiet -y 'ntfs-3g-2022.10.3'
dnf-3 install --quiet -y 'mkvtoolnix-93.0'
dnf-3 install --quiet -y 'ruby-3.4.5'
dnf-3 install --quiet -y 'xz-5.8.1'
dnf-3 install --quiet -y 'tk-devel-9.0.0'
dnf-3 install --quiet -y 'x265-4.1'
dnf-3 install --quiet -y 'x265-devel-4.1'
dnf-3 install --quiet -y 'llvm-20.1.8'
dnf-3 install --quiet -y 'docker-ce-28.3.3'
dnf-3 install --quiet -y 'docker-ce-cli-28.3.3'
dnf-3 install --quiet -y 'containerd.io-1.7.27'
dnf-3 install --quiet -y 'libcurl-devel-8.11.1'
dnf-3 install --quiet -y 'libxml2-devel-2.12.10'
dnf-3 install --quiet -y 'glib2-devel-2.84.4'
dnf-3 install --quiet -y 'gtk2-devel-2.24.33'
dnf-3 install --quiet -y 'libnotify-devel-0.8.6'
dnf-3 install --quiet -y 'libevent-devel-2.1.12'
dnf-3 install --quiet -y 'openssl-devel-3.2.4'
dnf-3 install --quiet -y 'zlib-ng-compat-devel-2.2.5'
dnf-3 install --quiet -y 'bzip2-devel-1.0.8'
dnf-3 install --quiet -y 'readline-devel-8.2'
dnf-3 install --quiet -y 'sqlite-devel-3.47.2'
dnf-3 install --quiet -y 'ncurses-devel-6.5'
dnf-3 install --quiet -y 'libffi-devel-3.4.6'
dnf-3 install --quiet -y 'xz-devel-5.8.1'
dnf-3 install --quiet -y 'autoconf-2.72'
dnf-3 install --quiet -y 'automake-1.17'
dnf-3 install --quiet -y 'libtool-2.5.4'
dnf-3 install --quiet -y 'pkgconf-pkg-config-2.3.0'
dnf-3 install --quiet -y 'yasm-1.3.0^20250625git121ab15'
dnf-3 install --quiet -y 'nasm-2.16.03'
dnf-3 install --quiet -y 'net-tools-2.0'
dnf-3 install --quiet -y 'bind-utils-9.18.38'
dnf-3 install --quiet -y 'b3sum-1.8.2'
dnf-3 install --quiet -y 'fd-find-10.2.0'
dnf-3 install --quiet -y 'fzf-0.65.1'
dnf-3 install --quiet -y 'digitemp-3.7.2'
dnf-3 install --quiet -y 'tuptime-5.2.4'
dnf-3 install --quiet -y 'duf-0.8.1'
dnf-3 install --quiet -y 'fswatch-1.17.1'
dnf-3 install --quiet -y 'buildbot-4.3.0'
dnf-3 install --quiet -y 'colordiff-1.0.21'
dnf-3 install --quiet -y 'cvs-1.11.23'
dnf-3 install --quiet -y 'cvs2cl-2.73'
dnf-3 install --quiet -y 'cvsps-2.2'
dnf-3 install --quiet -y 'darcs-2.18.2'
dnf-3 install --quiet -y 'dejagnu-1.6.3'
dnf-3 install --quiet -y 'diffstat-1.67'
dnf-3 install --quiet -y 'doxygen-1.13.2'
dnf-3 install --quiet -y 'expect-5.45.4'
dnf-3 install --quiet -y 'gambas3-ide-3.20.2'
dnf-3 install --quiet -y 'gettext-0.23.1'
dnf-3 install --quiet -y 'git-2.51.0'
dnf-3 install --quiet -y 'git-annex-10.20250320'
dnf-3 install --quiet -y 'git-cola-4.14.0'
dnf-3 install --quiet -y 'git2cl-3.0'
dnf-3 install --quiet -y 'gitg-45~20250512gitf7501bc'
dnf-3 install --quiet -y 'gtranslator-48.0'
dnf-3 install --quiet -y 'highlight-4.13'
dnf-3 install --quiet -y 'lcov-2.0'
dnf-3 install --quiet -y 'manedit-1.2.1'
dnf-3 install --quiet -y 'meld-3.23.0'
dnf-3 install --quiet -y 'monotone-1.1'
dnf-3 install --quiet -y 'myrepos-1.20180726'
dnf-3 install --quiet -y 'nemiver-0.9.6'
dnf-3 install --quiet -y 'patch-2.8'
dnf-3 install --quiet -y 'patchutils-0.4.2'
dnf-3 install --quiet -y 'qgit-2.10'
dnf-3 install --quiet -y 'quilt-0.69'
dnf-3 install --quiet -y 'rapidsvn-0.13.0'
dnf-3 install --quiet -y 'rcs-5.10.1'
dnf-3 install --quiet -y 'robodoc-4.99.44'
dnf-3 install --quiet -y 'scanmem-0.17'
dnf-3 install --quiet -y 'subunit-1.4.4'
dnf-3 install --quiet -y 'subversion-1.14.5'
dnf-3 install --quiet -y 'svn2cl-0.14'
dnf-3 install --quiet -y 'systemtap-5.3'
dnf-3 install --quiet -y 'tig-2.5.12'
dnf-3 install --quiet -y 'tortoisehg-7.0.1'
dnf-3 install --quiet -y 'translate-toolkit-3.14.5'
dnf-3 install --quiet -y 'utrac-0.3.0'

################################################################################
# Kernel
################################################################################
[ ! -f /etc/default/grub.bak ] && cp /etc/default/grub /etc/default/grub.bak
grep -q 'selinux=0' /etc/default/grub || sed -i '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/"$/ selinux=0"/' /etc/default/grub
echo "/etc/default/grub:" && diff -u /etc/default/grub.bak /etc/default/grub || true
grub2-mkconfig -o /boot/efi/EFI/fedora/grub.cfg
echo "/etc/kernel/cmdline:" && cat /etc/kernel/cmdline
echo "/proc/cmdline:" && cat /proc/cmdline
if [ -f /etc/selinux/config ]; then
  [ ! -f /etc/selinux/config.bak ] && cp /etc/selinux/config /etc/selinux/config.bak
  sed 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config >/etc/selinux/config.tmp
  mv /etc/selinux/config.tmp /etc/selinux/config
  diff -u /etc/selinux/config.bak /etc/selinux/config || true
  setenforce 0 2>/dev/null || true
fi
tee /etc/sysctl.d/99-disable-ipv6.conf <<'EOF'
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF

################################################################################
# Modules
################################################################################
tee /etc/modprobe.d/blacklist-sound.conf <<'EOF'
blacklist snd
blacklist snd_pcm
blacklist snd_seq
blacklist snd_hwdep
blacklist snd_timer
blacklist snd_pcm_oss
blacklist snd_bcm2835
blacklist snd_compress
blacklist snd_soc_core
blacklist snd_hda_core
blacklist snd_mixer_oss
blacklist snd_hda_intel
blacklist snd_hda_codec
blacklist snd_seq_device
blacklist snd_intel_dspcfg
blacklist snd_hda_codec_hdmi
blacklist snd_hda_codec_cirrus
blacklist snd_hda_codec_generic
blacklist soundcore
blacklist soundwire_intel
blacklist ledtrig_audio
EOF
tee /etc/modprobe.d/blacklist-video.conf <<'EOF'
blacklist nvidia
blacklist radeon
blacklist nouveau
EOF
tee /etc/modprobe.d/blacklist-wifi.conf <<'EOF'
blacklist b43
blacklist r8152
EOF
tee /etc/modprobe.d/blacklist-bluetooth.conf <<'EOF'
blacklist bluetooth
EOF
tee /etc/modprobe.d/brcmfmac-ignore.conf <<'EOF'
options brcmfmac fwload_disable=1
EOF
sudo udevadm control --reload
sudo udevadm trigger
dracut -f --quiet

################################################################################
# Services
################################################################################
systemctl list-units --type=service --state=running
services_to_enable=(
  docker
  chronyd
  NetworkManager
)
for _service in "${services_to_enable[@]}"; do
  if systemctl list-unit-files | grep -q "^$_service"; then
    systemctl enable "$_service"
    systemctl start "$_service"
    systemctl --no-pager status "$_service"
  else
    echo "Error: Service not found: $_service"
    exit 1
  fi
done
services_to_disable=(
  cups
  cups.path
  abrtd
  abrt-oops
  abrt-xorg
  abrt-journal-core
  polkit
  gssproxy
  firewalld
  bluetooth
  wpa_supplicant
  speakersafetyd
  systemd-vconsole-setup
  systemd-resolved
  ModemManager
)
for _service in "${services_to_disable[@]}"; do
  if systemctl list-unit-files | grep -q "^$_service"; then
    systemctl disable "$_service" 2>/dev/null
    systemctl mask "$_service"
    systemctl stop "$_service" 2>/dev/null
    echo "Disabled and masked: $_service"
  fi
done
systemctl list-units --type=service --state=running

################################################################################
# Network
################################################################################
tee /etc/NetworkManager/conf.d/10-no-wifi.conf >/dev/null <<'EOF'
[device]
wifi.scan-rand-mac-address=no

[radio]
wifi=disabled
EOF
mkdir -p /etc/tmpfiles.d
cat >/etc/tmpfiles.d/systemd-resolve.conf <<'EOF'
# Override to prevent recreation of /run/systemd/resolve
#d /run/systemd/resolve 0755 root root -
EOF
[ ! -f /etc/NetworkManager/NetworkManager.conf.bak ] && cp /etc/NetworkManager/NetworkManager.conf /etc/NetworkManager/NetworkManager.conf.bak
tee /etc/NetworkManager/NetworkManager.conf <<'EOF'
# Configuration file for NetworkManager.
#
# See "man 5 NetworkManager.conf" for details.
#
# The directories /usr/lib/NetworkManager/conf.d/ and /run/NetworkManager/conf.d/
# can contain additional .conf snippets installed by packages. These files are
# read before NetworkManager.conf and have thus lowest priority.
# The directory /etc/NetworkManager/conf.d/ can contain additional .conf
# snippets. Those snippets are merged last and overwrite the settings from this main
# file.
#
# The files within one conf.d/ directory are read in asciibetical order.
#
# You can prevent loading a file /usr/lib/NetworkManager/conf.d/NAME.conf
# by having a file NAME.conf in either /run/NetworkManager/conf.d/ or /etc/NetworkManager/conf.d/.
# Likewise, snippets from /run can be prevented from loading by placing
# a file with the same name in /etc/NetworkManager/conf.d/.
#
# If two files define the same key, the one that is read afterwards will overwrite
# the previous one.

[main]
#plugins=keyfile,ifcfg-rh
dns=default

[logging]
# When debugging NetworkManager, enabling debug logging is of great help.
#
# Logfiles contain no passwords and little sensitive information. But please
# check before posting the file online. You can also personally hand over the
# logfile to a NM developer to treat it confidential. Meet us on #nm on Libera.Chat.
#
# You can also change the log-level at runtime via
#   $ nmcli general logging level TRACE domains ALL
# However, usually it's cleaner to enable debug logging
# in the configuration and restart NetworkManager so that
# debug logging is enabled from the start.
#
# You will find the logfiles in syslog, for example via
#   $ journalctl -u NetworkManager
#
# Please post full logfiles for bug reports without pre-filtering or truncation.
# Also, for debugging the entire `journalctl` output can be interesting. Don't
# limit unnecessarily with `journalctl -u`. Exceptions are if you are worried
# about private data. Check before posting logfiles!
#
# Note that debug logging of NetworkManager can be quite verbose. Some messages
# might be rate-limited by the logging daemon (see RateLimitIntervalSec, RateLimitBurst
# in man journald.conf). Please disable rate-limiting before collecting debug logs!
#
#level=TRACE
#domains=ALL
EOF
diff -u /etc/NetworkManager/NetworkManager.conf.bak /etc/NetworkManager/NetworkManager.conf || true
if [ -L /etc/resolv.conf ] || [ -f /etc/resolv.conf ]; then
  rm -f /etc/resolv.conf
fi
ln -sf /run/NetworkManager/resolv.conf /etc/resolv.conf
mkdir -p /etc/systemd/system/NetworkManager.service.d
tee /etc/systemd/system/NetworkManager.service.d/override.conf <<'EOF'
[Unit]
After=
Requires=
EOF
systemctl daemon-reload
systemctl reenable NetworkManager
systemctl restart NetworkManager

################################################################################
# Locale
################################################################################
if ! locale -a | grep -q '^en_AU\.utf8$'; then
  localedef -i en_AU -f UTF-8 en_AU.UTF-8
fi
export LANG=en_AU.UTF-8
export LC_ALL=en_AU.UTF-8
locale

################################################################################
# Python
################################################################################
rm -rf /root/.pyenv || true
cp -rvf ${SERVICE_INSTALL}/pyenv /root/.pyenv
cd /root/.pyenv
./src/configure && make -C src
ln -s /root/.pyenv/libexec/pyenv /root/.pyenv/bin/pyenv
source /root/.bashrc
cd /tmp

################################################################################
# Monitoring
################################################################################
mkdir -p /home/graham/.config/htop
cat <<'EOF' >/home/graham/.config/htop/htoprc
fields=0 48 17 18 38 39 40 2 46 47 49 1
sort_key=46
sort_direction=-1
tree_sort_key=0
tree_sort_direction=1
hide_kernel_threads=1
hide_userland_threads=0
shadow_other_users=0
show_thread_names=0
show_program_path=1
highlight_base_name=1
highlight_megabytes=1
highlight_threads=1
highlight_changes=0
highlight_changes_delay_secs=5
find_comm_in_cmdline=1
strip_exe_from_cmdline=1
show_merged_command=0
tree_view=0
tree_view_always_by_pid=0
header_margin=1
detailed_cpu_time=0
cpu_count_from_one=0
show_cpu_usage=1
show_cpu_frequency=1
show_cpu_temperature=1
degree_fahrenheit=0
update_process_names=0
account_guest_in_cpu_meter=0
color_scheme=0
enable_mouse=1
delay=10
left_meters=LeftCPUs Memory Swap
left_meter_modes=1 1 1
right_meters=RightCPUs Tasks LoadAverage Uptime
right_meter_modes=1 2 2 2
hide_function_bar=0
EOF
chown -R graham:graham /home/graham/.config
mkdir -p /root/.config/htop && rm -rf /root/.config/htop/htoprc
ln -s /home/graham/.config/htop/htoprc /root/.config/htop/htoprc

################################################################################
# Time
################################################################################
cp -n /etc/chrony.conf /etc/chrony.conf.bak
for server in 0.au.pool.ntp.org 1.au.pool.ntp.org 2.au.pool.ntp.org 3.au.pool.ntp.org; do
  grep -q "^server $server" /etc/chrony.conf || echo "server $server iburst" | tee -a /etc/chrony.conf >/dev/null
done
diff -u /etc/chrony.conf.bak /etc/chrony.conf || true
systemctl restart chronyd
chronyc -a makestep
chronyc tracking
chronyc sources
chronyc -a sourcestats
chronyc -a activity

################################################################################
# Sensors
################################################################################
sensors-detect --auto

################################################################################
# Docker
################################################################################
mkdir -p /etc/systemd/system/docker.service.d
tee /etc/systemd/system/docker.service.d/override.conf <<'EOF'
[Unit]
After=NetworkManager.service
Requires=NetworkManager.service
EOF
systemctl daemon-reload
systemctl restart NetworkManager
systemctl restart docker
systemctl reenable NetworkManager docker
mkdir -p /etc/docker
cat <<'EOF' >/etc/docker/daemon.json
{
  "default-address-pools" : [
    {
      "base" : "172.16.0.0/12",
      "size" : 24
    }
  ]
}
EOF
systemctl restart docker
docker run --rm busybox ifconfig eth0
docker run --rm busybox nslookup google.com
docker run --rm busybox nslookup $(hostname)
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null || true
docker system prune --volumes -f 2>/dev/null

################################################################################
# Boot
################################################################################
BOOT_ERRORS=$(
  journalctl -b | grep -i error |
    grep -v "ACPI Error: Needed type" |
    grep -v "ACPI Error: AE_AML_OPERAND_TYPE" |
    grep -v "ACPI Error: Aborting method" |
    grep -v "20200925" |
    grep -v "remount-ro" | grep -v "smartd" |
    grep -v "Clock Unsynchronized" |
    grep -v "dockerd" | grep -v "containerd" |
    grep -v "/usr/lib/gnupg/scdaemon" |
    grep -v "Temporary failure in name resolution" |
    grep -v "dracut" |
    grep -v "brcmfmac" |
    grep -v "phy0" |
    grep -v "snd-pcm" || true
)
echo "################################################################################"
if [ "${BOOT_ERRORS}" == "" ]; then
  echo "No Boot errors, yay!"
else
  echo "Boot errors encountered, boo!"
  echo "################################################################################"
  echo "${BOOT_ERRORS}"
fi
echo "################################################################################"
