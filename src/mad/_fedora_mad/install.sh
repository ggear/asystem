#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

set -e
set -x

################################################################################
# Update
################################################################################
cd /tmp
dnf-3 update -y

################################################################################
# Packages
################################################################################
dnf-3 install -y jq-1.7.1
dnf-3 install -y yq-4.43.1
dnf-3 install -y nvme-cli-2.15
dnf-3 install -y acl-2.3.2
dnf-3 install -y parted-3.6
dnf-3 install -y util-linux-2.40.4
dnf-3 install -y usbutils-018
dnf-3 install -y smartmontools-7.5
dnf-3 install -y htop-3.4.1
dnf-3 install -y iotop-c-1.30
dnf-3 install -y ethtool-6.15
dnf-3 install -y lm_sensors-3.6.0
dnf-3 install -y efivar-39
dnf-3 install -y cifs-utils-7.2
dnf-3 install -y samba-4.22.4
dnf-3 install -y samba-client-4.22.4
dnf-3 install -y cups-2.4.12
dnf-3 install -y avahi-0.9~rc2
dnf-3 install -y inotify-tools-4.23.9.0
dnf-3 install -y powertop-2.15
dnf-3 install -y python3-3.13.7
dnf-3 install -y python3-pip-24.3.1
dnf-3 install -y vim-enhanced-9.1.1706
dnf-3 install -y nano-8.3
dnf-3 install -y screen-5.0.1
dnf-3 install -y tmux-3.5a
dnf-3 install -y curl-8.11.1
dnf-3 install -y wget2-wget-2.2.0
dnf-3 install -y unrar-0.3.1
dnf-3 install -y rsync-3.4.1
dnf-3 install -y mediainfo-25.04
dnf-3 install -y tesseract-5.5.0
dnf-3 install -y exfatprogs-1.2.9
dnf-3 install -y ntfs-3g-2022.10.3
dnf-3 install -y mkvtoolnix-93.0
dnf-3 install -y ruby-3.4.5
dnf-3 install -y xz-5.8.1
dnf-3 install -y tk-devel-9.0.0
dnf-3 install -y llvm-20.1.8
dnf-3 install -y docker-ce-28.3.3
dnf-3 install -y docker-ce-cli-28.3.3
dnf-3 install -y containerd.io-1.7.27
dnf-3 install -y libcurl-devel-8.11.1
dnf-3 install -y libxml2-devel-2.12.10
dnf-3 install -y glib2-devel-2.84.4
dnf-3 install -y gtk2-devel-2.24.33
dnf-3 install -y libnotify-devel-0.8.6
dnf-3 install -y libevent-devel-2.1.12
dnf-3 install -y openssl-devel-3.2.4
dnf-3 install -y zlib-ng-compat-devel-2.2.5
dnf-3 install -y bzip2-devel-1.0.8
dnf-3 install -y readline-devel-8.2
dnf-3 install -y sqlite-devel-3.47.2
dnf-3 install -y ncurses-devel-6.5
dnf-3 install -y libffi-devel-3.4.6
dnf-3 install -y xz-devel-5.8.1
dnf-3 install -y autoconf-2.72
dnf-3 install -y automake-1.17
dnf-3 install -y libtool-2.5.4
dnf-3 install -y pkgconf-pkg-config-2.3.0
dnf-3 install -y yasm-1.3.0^20250625git121ab15
dnf-3 install -y nasm-2.16.03
dnf-3 install -y net-tools-2.0
dnf-3 install -y bind-utils-9.18.38
dnf-3 install -y b3sum-1.8.2
dnf-3 install -y fd-find-10.2.0
dnf-3 install -y fzf-0.65.1
dnf-3 install -y digitemp-3.7.2
dnf-3 install -y tuptime-5.2.4
dnf-3 install -y duf-0.8.1
dnf-3 install -y fswatch-1.17.1
dnf-3 install -y buildbot-4.3.0
dnf-3 install -y colordiff-1.0.21
dnf-3 install -y cvs-1.11.23
dnf-3 install -y cvs2cl-2.73
dnf-3 install -y cvsps-2.2
dnf-3 install -y darcs-2.18.2
dnf-3 install -y dejagnu-1.6.3
dnf-3 install -y diffstat-1.67
dnf-3 install -y doxygen-1.13.2
dnf-3 install -y expect-5.45.4
dnf-3 install -y gambas3-ide-3.20.2
dnf-3 install -y gettext-0.23.1
dnf-3 install -y git-2.51.0
dnf-3 install -y git-annex-10.20250320
dnf-3 install -y git-cola-4.14.0
dnf-3 install -y git2cl-3.0
dnf-3 install -y gitg-45~20250512gitf7501bc
dnf-3 install -y gtranslator-48.0
dnf-3 install -y highlight-4.13
dnf-3 install -y lcov-2.0
dnf-3 install -y manedit-1.2.1
dnf-3 install -y meld-3.23.0
dnf-3 install -y monotone-1.1
dnf-3 install -y myrepos-1.20180726
dnf-3 install -y nemiver-0.9.6
dnf-3 install -y patch-2.8
dnf-3 install -y patchutils-0.4.2
dnf-3 install -y qgit-2.10
dnf-3 install -y quilt-0.69
dnf-3 install -y rapidsvn-0.13.0
dnf-3 install -y rcs-5.10.1
dnf-3 install -y robodoc-4.99.44
dnf-3 install -y scanmem-0.17
dnf-3 install -y subunit-1.4.4
dnf-3 install -y subversion-1.14.5
dnf-3 install -y svn2cl-0.14
dnf-3 install -y systemtap-5.3
dnf-3 install -y tig-2.5.12
dnf-3 install -y tortoisehg-7.0.1
dnf-3 install -y translate-toolkit-3.14.5
dnf-3 install -y utrac-0.3.0

################################################################################
# Kernel
################################################################################
[ ! -f /etc/default/grub.bak ] && cp /etc/default/grub /etc/default/grub.bak
grep -q 'selinux=0' /etc/default/grub || sed -i '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/"$/ selinux=0 systemd.unit=multi-user.target console=tty1"/' /etc/default/grub
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
tee /etc/sysctl.d/99-disable-ipv6.conf <<EOF
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF

################################################################################
# Modules
################################################################################
tee /etc/modprobe.d/blacklist-sound.conf <<EOF
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
tee /etc/modprobe.d/blacklist-video.conf <<EOF
blacklist nvidia
blacklist radeon
blacklist nouveau
EOF
tee /etc/modprobe.d/blacklist-wifi.conf <<EOF
blacklist b43
blacklist r8152
EOF
tee /etc/modprobe.d/blacklist-bluetooth.conf <<EOF
blacklist bluetooth
EOF
tee /etc/modprobe.d/brcmfmac-ignore.conf <<EOF
options brcmfmac fwload_disable=1
EOF
sudo udevadm control --reload
sudo udevadm trigger
dracut -f

################################################################################
# Services
################################################################################
systemctl list-units --type=service --state=running
services_to_enable=(
  docker
  chronyd
  systemd-resolved
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
  polkit
  gssproxy
  speakersafetyd
  firewalld
  bluetooth
  wpa_supplicant
  abrt-journal-core
  abrt-oops
  abrt-xorg
  abrtd
  systemd-vconsole-setup
  cups.path
  cups
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
tee /etc/NetworkManager/conf.d/10-no-wifi.conf >/dev/null <<EOF
[device]
wifi.scan-rand-mac-address=no

[radio]
wifi=disabled
EOF
mkdir -p /etc/tmpfiles.d
tee /etc/tmpfiles.d/systemd-resolve.conf <<EOF
d /run/systemd/resolve 0755 systemd-resolve systemd-resolve -
EOF
systemd-tmpfiles --create /etc/tmpfiles.d/systemd-resolve.conf
systemctl restart systemd-resolved

################################################################################
# Locale
################################################################################
if ! locale -a | grep -q '^en_AU\.utf8$'; then
  localedef -i en_AU -f UTF-8 en_AU.UTF-8
fi
export LANG=en_AU.UTF-8
export LC_ALL=en_AU.UTF-8
locale

#################################################################################
## Python
#################################################################################
#[[ ! -d /root/.pyenv ]] && git clone https://github.com/pyenv/pyenv.git /root/.pyenv
#cd /root/.pyenv
#git checkout master
#git pull --all
#git checkout v2.6.7
#
## TODO: Make this work
##git checkout ${PYENV_VERSION}
#
#./src/configure && make -C src
#source /root/.bashrc
#cd /tmp

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
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
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
    grep -v "brcmfmac" |
    grep -v "phy0" |
    grep -v "snd-pcm"
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
