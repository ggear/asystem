#!/bin/bash

SERVICE_HOME-/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL-/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

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
dnf-3 install -y iotop-
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
dnf-3 install -y vim-
dnf-3 install -y nano-8.3
dnf-3 install -y screen-5.0.1
dnf-3 install -y tmux-3.5a
dnf-3 install -y curl-8.11.1
dnf-3 install -y wget-
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
dnf-3 install -y zlib-devel-
dnf-3 install -y bzip2-devel-1.0.8
dnf-3 install -y readline-devel-8.2
dnf-3 install -y sqlite-devel-3.47.2
dnf-3 install -y ncurses-devel-6.5
dnf-3 install -y libffi-devel-3.4.6
dnf-3 install -y xz-devel-5.8.1
dnf-3 install -y autoconf-2.72
dnf-3 install -y automake-1.17
dnf-3 install -y libtool-2.5.4
dnf-3 install -y pkgconfig-
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
dnf-3 install -y git2cl-3.0
dnf-3 install -y git-annex-10.20250320
dnf-3 install -y git-cola-4.14.0
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
# Modules
################################################################################
tee /etc/modprobe.d/blacklist-sound.conf <<EOF
blacklist snd_pcm
blacklist snd_seq
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
for _service in docker; do
  systemctl enable ${_service}
  systemctl start ${_service}
  systemctl status ${_service}
done
for _service in ModemManager polkit gssproxy speakersafetyd firewalld bluetooth wpa_supplicant abrt-journal-core abrt-oops abrt-xorg abrtd systemd-vconsole-setup; do
  systemctl disable ${_service} 2>/dev/null
  systemctl mask ${_service}
  systemctl stop ${_service}
done
systemctl list-units --type=service --state=running

################################################################################
# Network
################################################################################
nmcli radio wifi off
wifi_dev=$(nmcli -t -f DEVICE,TYPE device | grep ':wifi' | cut -d: -f1 | grep -v '^p2p')
tee /etc/NetworkManager/conf.d/10-no-wifi.conf >/dev/null <<EOF
[device]
wifi.scan-rand-mac-address=no

[keyfile]
unmanaged-devices=interface-name:$wifi_dev
EOF

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
## Disable hardware
#################################################################################
#[ ! -f /etc/modprobe.d/blacklist-b43.conf ] && echo "blacklist b43" | tee -a /etc/modprobe.d/blacklist-b43.conf
#[ ! -f /etc/modprobe.d/blacklist-r8152.conf ] && echo "blacklist r8152" | tee /etc/modprobe.d/blacklist-r8152.conf
#[ ! -f /etc/modprobe.d/blacklist-btusb.conf ] && echo "blacklist btusb" | tee -a /etc/modprobe.d/blacklist-btusb.conf
#if [ ! -f /etc/modprobe.d/blacklist-video.conf ]; then
#  echo "blacklist nvidia" | tee -a /etc/modprobe.d/blacklist-video.conf
#  echo "blacklist radeon" | tee -a /etc/modprobe.d/blacklist-video.conf
#  echo "blacklist nouveau" | tee -a /etc/modprobe.d/blacklist-video.conf
#fi
#if [ ! -f /etc/modprobe.d/blacklist-snd.conf ]; then
#  echo "blacklist soundcore" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_timer" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_pcm" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hwdep" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_core" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_codec" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_compress" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_soc_core" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist soundwire_intel" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_intel_dspcfg" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_intel" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_codec_hdmi" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist ledtrig_audio" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_codec_generic" | tee -a /etc/modprobe.d/blacklist-snd.conf
#  echo "blacklist snd_hda_codec_cirrus" | tee -a /etc/modprobe.d/blacklist-snd.conf
#fi
#update-initramfs -u -k all
#
#################################################################################
## Defaults
#################################################################################
#if [ $(grep "net.ipv6.conf.all.disable_ipv6" /etc/sysctl.conf | wc -l) -eq 0 ]; then
#  echo "net.ipv6.conf.all.disable_ipv6 = 1" >>/etc/sysctl.conf
#  sysctl -p
#fi
#if [ $(grep "vm.swappiness" /etc/sysctl.conf | wc -l) -eq 0 ]; then
#  echo "vm.swappiness = 1" >>/etc/sysctl.conf
#  sysctl vm.swappiness=1
#fi
#
#################################################################################
## Network
#################################################################################
#mkdir -p /etc/network
#INTERFACE=$(lshw -C network -short -c network 2>/dev/null | grep -i ethernet | tr -s ' ' | cut -d' ' -f2 | grep -v 'path\|=\|network')
#if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "auto eth0." /etc/network/interfaces | wc -l) -eq 0 ]; then
#  MACADDRESS_SUFFIX="$(ifconfig "${INTERFACE}" | grep ether | tr -s ' ' | cut -d' ' -f3 | cut -d':' -f2-)"
#  if [ "${INTERFACE}" != "" ]; then
#    cat <<EOF >/etc/network/interfaces
## interfaces(5) file used by ifup(8) and ifdown(8)
## Include files from /etc/network/interfaces.d:
#
#source /etc/network/interfaces.d/*
#
#rename ${INTERFACE}=eth0
#
#auto eth0
#iface eth0 inet dhcp
#
##auto eth0.3
##iface eth0.3 inet dhcp
##    vlan-raw-device eth0
##    pre-up ip link set eth0.3 address 3a:${MACADDRESS_SUFFIX}
##
##auto eth0.4
##iface eth0.4 inet dhcp
##    vlan-raw-device eth0
##    pre-up ip link set eth0.4 address 4a:${MACADDRESS_SUFFIX}
#
#EOF
#  fi
#fi
#systemctl start networking
#systemctl enable networking
#systemctl status networking
#systemctl stop NetworkManager
#systemctl disable NetworkManager
#systemctl mask NetworkManager
#systemctl stop ModemManager
#systemctl disable ModemManager
#systemctl mask ModemManager
#systemctl stop systemd-networkd
#systemctl disable systemd-networkd
#systemctl mask systemd-networkd
#systemctl stop wpa_supplicant
#systemctl disable wpa_supplicant
#systemctl mask wpa_supplicant
#grep -q '^8021q' /etc/modules 2>/dev/null || echo '8021q' | tee -a /etc/modules
#grep -q '^macvlan' /etc/modules 2>/dev/null || echo 'macvlan' | tee -a /etc/modules
#grep -q '^blacklist applesmc' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist applesmc' | tee -a /etc/modprobe.d/blacklist-applesmc.conf
#grep -q '^blacklist bcma-pci-bridge' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist bcma-pci-bridge' | tee -a /etc/modprobe.d/blacklist-wifi.conf
#
#################################################################################
## Power
#################################################################################
#cat <<'EOF' >/etc/systemd/system/powertop.service
#[Unit]
#Description=PowerTOP auto tune
#
#[Service]
#Type=oneshot
#Environment="TERM=dumb"
#RemainAfterExit=true
#ExecStart=/usr/sbin/powertop --auto-tune
#
#[Install]
#WantedBy=multi-user.target
#EOF
#systemctl daemon-reload
#systemctl enable powertop
## INFO: Warning, this is aggressive and overides the below keyboard udev rule such the keyboard goes to sleep all the time, annoying!
##systemctl stop powertop
##systemctl disable powertop
#
#################################################################################
## Keyboard
#################################################################################
#echo 'ACTION=="add", SUBSYSTEM=="usb", KERNEL=="1-1.4.1", ATTR{idVendor}=="04d9", ATTR{idProduct}=="0006", ATTR{power/control}="on"' | tee /etc/udev/rules.d/99-holtek-keyboard.rules >/dev/null
#udevadm control --reload
#udevadm trigger
#
#################################################################################
## Bluetooth
#################################################################################
#systemctl stop bluetooth.service
#systemctl disable bluetooth.service
#systemctl mask bluetooth.service
#grep -q '^blacklist bluetooth' /etc/modprobe.d/blacklist-bluetooth.conf 2>/dev/null || echo 'blacklist bluetooth' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf
#
#################################################################################
## Sound
#################################################################################
#BLACKLIST_FILE="/etc/modprobe.d/alsa-blacklist.conf"
#MODULES=(
#  snd_bcm2835
#  snd_pcm
#  snd_seq
#  snd_timer
#  snd
#  snd_soc_core
#  snd_seq_device
#  snd_pcm_oss
#  snd_mixer_oss
#)
#[ ! -f "$BLACKLIST_FILE" ] && touch "$BLACKLIST_FILE"
#for mod in "${MODULES[@]}"; do
#  grep -qx "$mod" "$BLACKLIST_FILE" || echo "blacklist $mod" | tee -a "$BLACKLIST_FILE" >/dev/null
#done
#systemctl mask alsa-utils.service alsa-restore.service alsa-state.service
#
#################################################################################
## Monitoring
#################################################################################
#mkdir -p /home/graham/.config/htop
#cat <<'EOF' >/home/graham/.config/htop/htoprc
#fields=0 48 17 18 38 39 40 2 46 47 49 1
#sort_key=46
#sort_direction=-1
#tree_sort_key=0
#tree_sort_direction=1
#hide_kernel_threads=1
#hide_userland_threads=0
#shadow_other_users=0
#show_thread_names=0
#show_program_path=1
#highlight_base_name=1
#highlight_megabytes=1
#highlight_threads=1
#highlight_changes=0
#highlight_changes_delay_secs=5
#find_comm_in_cmdline=1
#strip_exe_from_cmdline=1
#show_merged_command=0
#tree_view=0
#tree_view_always_by_pid=0
#header_margin=1
#detailed_cpu_time=0
#cpu_count_from_one=0
#show_cpu_usage=1
#show_cpu_frequency=1
#show_cpu_temperature=1
#degree_fahrenheit=0
#update_process_names=0
#account_guest_in_cpu_meter=0
#color_scheme=0
#enable_mouse=1
#delay=10
#left_meters=LeftCPUs Memory Swap
#left_meter_modes=1 1 1
#right_meters=RightCPUs Tasks LoadAverage Uptime
#right_meter_modes=1 2 2 2
#hide_function_bar=0
#EOF
#chown -R graham:graham /home/graham/.config
#mkdir -p /root/.config/htop && rm -rf /root/.config/htop/htoprc
#ln -s /home/graham/.config/htop/htoprc /root/.config/htop/htoprc
#
#################################################################################
## Time
#################################################################################
#systemctl mask systemd-timesyncd.service
#timedatectl set-timezone "Australia/Perth"
#sed -i 's/0.debian.pool.ntp.org/216.239.35.0/g' /etc/ntpsec/ntp.conf
#sed -i 's/1.debian.pool.ntp.org/216.239.35.4/g' /etc/ntpsec/ntp.conf
#sed -i 's/2.debian.pool.ntp.org/216.239.35.8/g' /etc/ntpsec/ntp.conf
#sed -i 's/3.debian.pool.ntp.org/216.239.35.12/g' /etc/ntpsec/ntp.conf
#mkdir -p /var/log/ntpsec
#chown ntpsec:ntpsec /var/log/ntpsec
#systemctl daemon-reload
#systemctl restart ntpsec.service
#systemctl status ntpsec.service
#ntpq -p
#
#################################################################################
## Python
#################################################################################
#if [ ! -d /root/.pyenv ]; then
#  git clone https://github.com/pyenv/pyenv.git /root/.pyenv
#fi
#cd /root/.pyenv
#git checkout master
#git pull --all
#git checkout v2.6.5
#./src/configure && make -C src
#source /root/.bashrc
#cd /tmp
#
#################################################################################
## Temperature
#################################################################################
#sensors-detect --auto
#
#################################################################################
## Printing
#################################################################################
#systemctl stop cups
#systemctl disable cups
#systemctl mask cups
#
#################################################################################
## Docker
#################################################################################
#[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
#docker system prune --volumes -f 2>/dev/null
#mkdir -p /etc/docker
#cat <<'EOF' >/etc/docker/daemon.json
#{
#  "default-address-pools" : [
#    {
#      "base" : "172.16.0.0/12",
#      "size" : 24
#    }
#  ]
#}
#EOF
#
#################################################################################
## Uptime
#################################################################################
#tuptime

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
