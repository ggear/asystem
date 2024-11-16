#!/bin/bash

################################################################################
# Packages upgrade
################################################################################
cd /tmp
apt-get update
apt-get upgrade -y --without-new-pkgs

################################################################################
# Packages install (from update script)
################################################################################
apt-get install -y --allow-downgrades 'jq=1.6-2.1'
apt-get install -y --allow-downgrades 'xq=1.0.0-2+b5'
apt-get install -y --allow-downgrades 'duf=0.8.1-1+b6'
apt-get install -y --allow-downgrades 'ntp=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1+deb12u1'
apt-get install -y --allow-downgrades 'psmisc=23.6-1'
apt-get install -y --allow-downgrades 'usbutils=1:014-1+deb12u1'
apt-get install -y --allow-downgrades 'dnsutils=1:9.18.28-1~deb12u2'
apt-get install -y --allow-downgrades 'ntpdate=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1+deb12u1'
apt-get install -y --allow-downgrades 'ntfs-3g=1:2022.10.3-1+b1'
apt-get install -y --allow-downgrades 'acl=2.3.1-3'
apt-get install -y --allow-downgrades 'unrar=1:6.2.6-1+deb12u1'
apt-get install -y --allow-downgrades 'rsync=3.2.7-1'
apt-get install -y --allow-downgrades 'vim=2:9.0.1378-2'
apt-get install -y --allow-downgrades 'rename=2.01-1'
apt-get install -y --allow-downgrades 'parted=3.5-3'
apt-get install -y --allow-downgrades 'curl=7.88.1-10+deb12u7'
apt-get install -y --allow-downgrades 'screen=4.9.0-4'
apt-get install -y --allow-downgrades 'fswatch=1.14.0+repack-13.1+b1'
apt-get install -y --allow-downgrades 'util-linux=2.38.1-5+deb12u1'
apt-get install -y --allow-downgrades 'mediainfo=23.04-1'
apt-get install -y --allow-downgrades 'digitemp=3.7.2-2'
apt-get install -y --allow-downgrades 'tuptime=5.2.2'
apt-get install -y --allow-downgrades 'bsdmainutils=12.1.8'
apt-get install -y --allow-downgrades 'netselect-apt=0.3.ds1-30.1'
apt-get install -y --allow-downgrades 'smartmontools=7.3-1+b1'
apt-get install -y --allow-downgrades 'avahi-daemon=0.8-10'
apt-get install -y --allow-downgrades 'avahi-utils=0.8-10'
apt-get install -y --allow-downgrades 'net-tools=2.10-0.1'
apt-get install -y --allow-downgrades 'ethtool=1:6.1-1'
apt-get install -y --allow-downgrades 'lm-sensors=1:3.6.0-7.1'
apt-get install -y --allow-downgrades 'efivar=37-6'
apt-get install -y --allow-downgrades 'apt-transport-https=2.6.1'
apt-get install -y --allow-downgrades 'ca-certificates=20230311'
apt-get install -y --allow-downgrades 'gnupg-agent=2.2.40-1.1'
apt-get install -y --allow-downgrades 'software-properties-common=0.99.30-4.1~deb12u1'
apt-get install -y --allow-downgrades 'mkvtoolnix=74.0.0-1'
apt-get install -y --allow-downgrades 'docker-ce=5:27.3.1-1~debian.12~bookworm'
apt-get install -y --allow-downgrades 'docker-ce-cli=5:27.3.1-1~debian.12~bookworm'
apt-get install -y --allow-downgrades 'containerd.io=1.7.22-1'
apt-get install -y --allow-downgrades 'cifs-utils=2:7.0-2'
apt-get install -y --allow-downgrades 'samba=2:4.17.12+dfsg-0+deb12u1'
apt-get install -y --allow-downgrades 'cups=2.4.2-3+deb12u8'
apt-get install -y --allow-downgrades 'smbclient=2:4.17.12+dfsg-0+deb12u1'
apt-get install -y --allow-downgrades 'inotify-tools=3.22.6.0-4'
apt-get install -y --allow-downgrades 'htop=3.2.2-2'
apt-get install -y --allow-downgrades 'iotop=0.6-42-ga14256a-0.1+b2'
apt-get install -y --allow-downgrades 'hdparm=9.65+ds-1'
apt-get install -y --allow-downgrades 'stress-ng=0.15.06-2'
apt-get install -y --allow-downgrades 'memtester=4.6.0-1'
apt-get install -y --allow-downgrades 'linux-cpupower=6.1.112-1'
apt-get install -y --allow-downgrades 'firmware-linux-nonfree=20230210-5'
apt-get install -y --allow-downgrades 'hwinfo=21.82-1'
apt-get install -y --allow-downgrades 'lshw=02.19.git.2021.06.19.996aaad9c7-2+b1'
apt-get install -y --allow-downgrades 'vlan=2.0.5'
apt-get install -y --allow-downgrades 'powertop=2.14-1+b2'
apt-get install -y --allow-downgrades 'locales=2.36-9+deb12u8'
apt-get install -y --allow-downgrades 'python3=3.11.2-1+b1'
apt-get install -y --allow-downgrades 'python3-pip=23.0.1+dfsg-1'
apt-get install -y --allow-downgrades 'tesseract-ocr=5.3.0-2'
apt-get install -y --allow-downgrades 'libedgetpu1-std=16.0'
apt-get install -y --allow-downgrades 'exfatprogs=1.2.0-1+deb12u1'
apt-get install -y --allow-downgrades 'build-essential=12.9'
apt-get install -y --allow-downgrades 'automake=1:1.16.5-1.3'
apt-get install -y --allow-downgrades 'autoconf=2.71-3'
apt-get install -y --allow-downgrades 'checkinstall=1.6.2+git20170426.d24a630-3+b1'
apt-get install -y --allow-downgrades 'libtool=2.4.7-7~deb12u1'
apt-get install -y --allow-downgrades 'pkg-config=1.8.1-1'
apt-get install -y --allow-downgrades 'intltool=0.51.0-6'
apt-get install -y --allow-downgrades 'yasm=1.3.0-4'
apt-get install -y --allow-downgrades 'nasm=2.16.01-1'
apt-get install -y --allow-downgrades 'ruby-full=1:3.1'
apt-get install -y --allow-downgrades 'xz-utils=5.4.1-0.2'
apt-get install -y --allow-downgrades 'tk-dev=8.6.13'
apt-get install -y --allow-downgrades 'zlib1g-dev=1:1.2.13.dfsg-1'
apt-get install -y --allow-downgrades 'llvm=1:14.0-55.7~deb12u1'
apt-get install -y --allow-downgrades 'libssl-dev=3.0.14-1~deb12u2'
apt-get install -y --allow-downgrades 'libbz2-dev=1.0.8-5+b1'
apt-get install -y --allow-downgrades 'libreadline-dev=8.2-1.3'
apt-get install -y --allow-downgrades 'libsqlite3-dev=3.40.1-2'
apt-get install -y --allow-downgrades 'libncurses5-dev=6.4-4'
apt-get install -y --allow-downgrades 'libncursesw5-dev=6.4-4'
apt-get install -y --allow-downgrades 'libffi-dev=3.4.4-1'
apt-get install -y --allow-downgrades 'liblzma-dev=5.4.1-0.2'
apt-get install -y --allow-downgrades 'libxml2-dev=2.9.14+dfsg-1.3~deb12u1'
apt-get install -y --allow-downgrades 'libgtk2.0-dev=2.24.33-2+deb12u1'
apt-get install -y --allow-downgrades 'libnotify-dev=0.8.1-1'
apt-get install -y --allow-downgrades 'libglib2.0-dev=2.74.6-2+deb12u3'
apt-get install -y --allow-downgrades 'libevent-dev=2.1.12-stable-8'
apt-get install -y --allow-downgrades 'libcurl4-openssl-dev=7.88.1-10+deb12u7'

################################################################################
# Grub config
################################################################################
if [ -f /etc/default/grub ] && [ $(grep "GRUB_TIMEOUT=10" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_TIMEOUT=5/GRUB_TIMEOUT=10/' /etc/default/grub
  update-grub
fi
if [ -f /etc/default/grub ] && [ $(grep "cdgroup_enable=memory swapaccount=1" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="cdgroup_enable=memory swapaccount=1"/' /etc/default/grub
  update-grub
fi

################################################################################
# Packages purge
################################################################################
systemctl stop unattended-upgrades
systemctl disable unattended-upgrades
apt-get remove --assume-yes --purge unattended-upgrades
apt-get -y --purge autoremove

################################################################################
# Localisation
################################################################################
export LANGUAGE=en_AU.UTF-8
export LANG=en_AU.UTF-8
export LC_ALL=en_AU.UTF-8
locale-gen en_AU.UTF-8

################################################################################
# Shell setup
################################################################################
cat <<EOF >"${HOME}/.bashrc"
# .bashrc

export LC_COLLATE=C
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
alias ls='ls \$LS_OPTIONS'
alias uptime=tuptime

EOF

################################################################################
# Disable hardware
################################################################################
[ ! -f /etc/modprobe.d/blacklist-b43.conf ] && echo "blacklist b43" | tee -a /etc/modprobe.d/blacklist-b43.conf
[ ! -f /etc/modprobe.d/blacklist-btusb.conf ] && echo "blacklist btusb" | tee -a /etc/modprobe.d/blacklist-btusb.conf
if [ ! -f /etc/modprobe.d/blacklist-video.conf ]; then
  echo "blacklist nvidia" | tee -a /etc/modprobe.d/blacklist-video.conf
  echo "blacklist radeon" | tee -a /etc/modprobe.d/blacklist-video.conf
  echo "blacklist nouveau" | tee -a /etc/modprobe.d/blacklist-video.conf
fi
if [ ! -f /etc/modprobe.d/blacklist-snd.conf ]; then
  echo "blacklist soundcore" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_timer" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_pcm" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hwdep" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_core" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_codec" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_compress" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_soc_core" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist soundwire_intel" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_intel_dspcfg" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_intel" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_codec_hdmi" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist ledtrig_audio" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_codec_generic" | tee -a /etc/modprobe.d/blacklist-snd.conf
  echo "blacklist snd_hda_codec_cirrus" | tee -a /etc/modprobe.d/blacklist-snd.conf
fi

################################################################################
# Defaults
################################################################################
if [ $(grep "net.ipv6.conf.all.disable_ipv6" /etc/sysctl.conf | wc -l) -eq 0 ]; then
  echo "net.ipv6.conf.all.disable_ipv6 = 1" >>/etc/sysctl.conf
  sysctl -p
fi
if [ $(grep "vm.swappiness" /etc/sysctl.conf | wc -l) -eq 0 ]; then
  echo "vm.swappiness = 1" >>/etc/sysctl.conf
  sysctl vm.swappiness=1
fi

################################################################################
# Shell
################################################################################
if [ $(grep "history-search" /etc/bash.bashrc | wc -l) -eq 0 ]; then
  echo "" >>/etc/bash.bashrc
  echo "bind '\"\e[A\":history-search-backward'" >>/etc/bash.bashrc
  echo "bind '\"\e[B\":history-search-forward'" >>/etc/bash.bashrc
fi

################################################################################
# Power
################################################################################
cat <<EOF >/etc/systemd/system/powertop.service
[Unit]
Description=PowerTOP auto tune

[Service]
Type=oneshot
Environment="TERM=dumb"
RemainAfterExit=true
ExecStart=/usr/sbin/powertop --auto-tune

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable powertop.service

################################################################################
# Monitoring
################################################################################
mkdir -p /home/graham/.config/htop
cat <<EOF >/home/graham/.config/htop/htoprc
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
# Network
################################################################################
cat <<EOF >/etc/avahi/avahi-daemon.conf
[server]
use-ipv6=no
allow-interfaces=lan0
[publish]
publish-hinfo=no
publish-workstation=no
[reflector]
enable-reflector=no
EOF
#systemctl disable avahi-daemon.socket
#systemctl disable avahi-daemon.service
#systemctl stop avahi-daemon.service
systemctl enable avahi-daemon.socket
systemctl enable avahi-daemon.service
systemctl restart avahi-daemon.service
systemctl status avahi-daemon.service
avahi-browse -a -t
avahi-browse _home-assistant._tcp -t -r
#avahi-browse _home-assistant._tcp -r
#avahi-publish -v -s "Home1" _home-assistant._tcp 32401 "HACK"
#dns-sd -L Home _home-assistant._tcp local

################################################################################
# Time
################################################################################
systemctl mask systemd-timesyncd.service
timedatectl set-timezone "Australia/Perth"
sed -i 's/0.debian.pool.ntp.org/216.239.35.0/g' /etc/ntpsec/ntp.conf
sed -i 's/1.debian.pool.ntp.org/216.239.35.4/g' /etc/ntpsec/ntp.conf
sed -i 's/2.debian.pool.ntp.org/216.239.35.8/g' /etc/ntpsec/ntp.conf
sed -i 's/3.debian.pool.ntp.org/216.239.35.12/g' /etc/ntpsec/ntp.conf
mkdir -p /var/log/ntpsec
chown ntpsec:ntpsec /var/log/ntpsec
systemctl daemon-reload
systemctl restart ntpsec.service
systemctl status ntpsec.service
ntpq -p

################################################################################
# Python
################################################################################
if [ ! -d /root/.pyenv ]; then
  git clone https://github.com/pyenv/pyenv.git /root/.pyenv
fi
cd /root/.pyenv
git checkout master
git pull --all
git checkout v2.4.3
./src/configure && make -C src
if [ $(grep "pyenv" /root/.bashrc | wc -l) -eq 0 ]; then
  echo $'export PATH=$PATH:/root/.pyenv/bin\n' >>/root/.bashrc
fi
source /root/.bashrc
cd /tmp

################################################################################
# Temperature
################################################################################
sensors-detect --auto

################################################################################
# Printing
################################################################################
if [ ! -d /opt/brother/drivers ]; then
  systemctl stop cups
  systemctl disable cups
fi

################################################################################
# Docker
################################################################################
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
docker system prune --volumes -f 2>/dev/null
mkdir -p /etc/docker
cat <<EOF >/etc/docker/daemon.json
{
  "default-address-pools" : [
    {
      "base" : "172.16.0.0/12",
      "size" : 24
    }
  ]
}
EOF

################################################################################
# Devices
################################################################################
cat <<EOF >/etc/udev/rules.d/98-usb-edgetpu.rules
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a6e", ATTRS{idProduct}=="089a", MODE="0664", TAG+="uaccess"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="18d1", ATTRS{idProduct}=="9302", MODE="0664", TAG+="uaccess"
EOF
chmod -x /etc/udev/rules.d/98-usb-edgetpu.rules
lsusb
for DEV in $(find /dev -name ttyUSB?); do
  udevadm info ${DEV} | grep "P: "
  udevadm info -a -n ${DEV} | grep {idVendor} | head -1
  udevadm info -a -n ${DEV} | grep {idProduct} | head -1
  udevadm info -a -n ${DEV} | grep {serial} | head -1
  udevadm info -a -n ${DEV} | grep {product} | head -1
done
cat <<EOF >/etc/udev/rules.d/99-usb-serial.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", ATTRS{product}=="USB-Serial Controller", SYMLINK+="ttyUSBTempProbe"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{product}=="CP2102 USB to UART Bridge Controller", SYMLINK+="ttyUSBVantagePro2"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{product}=="Sonoff Zigbee 3.0 USB Dongle Plus", SYMLINK+="ttyUSBZB3DongleP"
EOF
chmod -x /etc/udev/rules.d/99-usb-serial.rules
udevadm control --reload-rules && udevadm trigger && sleep 2
ls -la /dev/ttyUSB*

################################################################################
# Digitemp
################################################################################
if [ -L /dev/ttyUSBTempProbe ]; then
  mkdir -p /etc/digitemp
  digitemp_DS9097 -i -s /dev/ttyUSBTempProbe -c /etc/digitemp/temp_probe.conf
  digitemp_DS9097 -a -c /etc/digitemp/temp_probe.conf
else
  rm -rf /etc/digitemp*
fi

################################################################################
# Uptime
################################################################################
tuptime

################################################################################
# Boot
################################################################################
#BOOT_ERRORS=$(
#  journalctl -b | grep -i error |
#    grep -v "ACPI Error: Needed type" |
#    grep -v "ACPI Error: AE_AML_OPERAND_TYPE" |
#    grep -v "ACPI Error: Aborting method" |
#    grep -v "20200925" |
#    grep -v "remount-ro" | grep -v "smartd" |
#    grep -v "Clock Unsynchronized" |
#    grep -v "dockerd" | grep -v "containerd" |
#    grep -v "/usr/lib/gnupg/scdaemon" |
#    grep -v "Temporary failure in name resolution"
#)
#echo "################################################################################"
#if [ "${BOOT_ERRORS}" == "" ]; then
#  echo "No Boot errors, yay!"
#else
#  echo "Boot errors encountered, boo!"
#  echo "################################################################################"
#  echo "${BOOT_ERRORS}"
#fi
#echo "################################################################################" || [ "${BOOT_ERRORS}" == "" ]
