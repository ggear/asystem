#!/bin/bash

################################################################################
# Packages upgrade
################################################################################
apt update
apt upgrade -y --without-new-pkgs

################################################################################
# Packages install (from update script)
################################################################################
apt install -y --allow-downgrades 'jq=1.6-2.1'
apt install -y --allow-downgrades 'ntp=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1'
apt install -y --allow-downgrades 'usbutils=1:014-1'
apt install -y --allow-downgrades 'dnsutils=1:9.18.12-1'
apt install -y --allow-downgrades 'ntpdate=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1'
apt install -y --allow-downgrades 'ntfs-3g=1:2022.10.3-1+b1'
apt install -y --allow-downgrades 'acl=2.3.1-3'
apt install -y --allow-downgrades 'unrar=1:6.2.6-1'
apt install -y --allow-downgrades 'rsync=3.2.7-1'
apt install -y --allow-downgrades 'vim=2:9.0.1378-2'
apt install -y --allow-downgrades 'rename=2.01-1'
apt install -y --allow-downgrades 'curl=7.88.1-10'
apt install -y --allow-downgrades 'screen=4.9.0-4'
apt install -y --allow-downgrades 'fswatch=1.14.0+repack-13.1+b1'
apt install -y --allow-downgrades 'util-linux=2.38.1-5+b1'
apt install -y --allow-downgrades 'mediainfo=23.04-1'
apt install -y --allow-downgrades 'bsdmainutils=12.1.8'
apt install -y --allow-downgrades 'netselect-apt=0.3.ds1-30.1'
apt install -y --allow-downgrades 'smartmontools=7.3-1+b1'
apt install -y --allow-downgrades 'avahi-daemon=0.8-10'
apt install -y --allow-downgrades 'avahi-utils=0.8-10'
apt install -y --allow-downgrades 'net-tools=2.10-0.1'
apt install -y --allow-downgrades 'ethtool=1:6.1-1'
apt install -y --allow-downgrades 'lm-sensors=1:3.6.0-7.1'
apt install -y --allow-downgrades 'apt-transport-https=2.6.1'
apt install -y --allow-downgrades 'ca-certificates=20230311'
apt install -y --allow-downgrades 'gnupg-agent=2.2.40-1.1'
apt install -y --allow-downgrades 'software-properties-common=0.99.30-4'
apt install -y --allow-downgrades 'mkvtoolnix=74.0.0-1'
apt install -y --allow-downgrades 'docker-ce=5:24.0.2-1~debian.12~bookworm'
apt install -y --allow-downgrades 'docker-ce-cli=5:24.0.2-1~debian.12~bookworm'
apt install -y --allow-downgrades 'containerd.io=1.6.21-1'
apt install -y --allow-downgrades 'cifs-utils=2:7.0-2'
apt install -y --allow-downgrades 'samba=2:4.17.8+dfsg-2'
apt install -y --allow-downgrades 'cups=2.4.2-3'
apt install -y --allow-downgrades 'smbclient=2:4.17.8+dfsg-2'
apt install -y --allow-downgrades 'inotify-tools=3.22.6.0-4'
apt install -y --allow-downgrades 'htop=3.2.2-2'
apt install -y --allow-downgrades 'iotop=0.6-42-ga14256a-0.1+b2'
apt install -y --allow-downgrades 'hdparm=9.65+ds-1'
apt install -y --allow-downgrades 'stress-ng=0.15.06-2'
apt install -y --allow-downgrades 'memtester=4.6.0-1'
apt install -y --allow-downgrades 'linux-cpupower=6.1.27-1'
apt install -y --allow-downgrades 'firmware-linux-nonfree=20230210-5'
apt install -y --allow-downgrades 'hwinfo=21.82-1'
apt install -y --allow-downgrades 'lshw=02.19.git.2021.06.19.996aaad9c7-2+b1'
apt install -y --allow-downgrades 'vlan=2.0.5'
apt install -y --allow-downgrades 'ffmpeg=7:5.1.3-1'
apt install -y --allow-downgrades 'powertop=2.14-1+b2'
apt install -y --allow-downgrades 'locales=2.36-9'
apt install -y --allow-downgrades 'python3=3.11.2-1+b1'
apt install -y --allow-downgrades 'python3-pip=23.0.1+dfsg-1'

################################################################################
# Packages purge
################################################################################
systemctl stop unattended-upgrades
systemctl disable unattended-upgrades
apt remove --assume-yes --purge unattended-upgrades
apt -y --purge autoremove

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
if [ -f "${HOME}/.bashrc" ]; then
  cat <<EOF >"${HOME}/.bashrc"
# .bashrc

export LC_COLLATE=C
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad
export LS_OPTIONS='--color=auto'
alias ls='ls \$LS_OPTIONS'

EOF
fi

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
sed -i 's/0.debian.pool.ntp.org/216.239.35.0/g' /etc/ntp.conf
sed -i 's/1.debian.pool.ntp.org/216.239.35.4/g' /etc/ntp.conf
sed -i 's/2.debian.pool.ntp.org/216.239.35.8/g' /etc/ntp.conf
sed -i 's/3.debian.pool.ntp.org/216.239.35.12/g' /etc/ntp.conf
systemctl daemon-reload
systemctl restart ntp.service
systemctl status ntp.service
ntpq -p

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
rm -rf /usr/local/bin/docker-compose
pip uninstall --break-system-packages -y docker-compose
pip install --break-system-packages --no-input docker-compose==1.29.2
docker-compose -v
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
docker system prune --volumes -f 2>/dev/null
if [ -f /etc/default/grub ] && [ $(grep "cdgroup_enable=memory swapaccount=1" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="cdgroup_enable=memory swapaccount=1"/' /etc/default/grub
  update-grub
fi

################################################################################
# Boot
################################################################################
BOOT_ERRORS=$(
  journalctl -b | grep -i error |
    grep -v "20200925" |
    grep -v "remount-ro" | grep -v "smartd" |
    grep -v "Clock Unsynchronized" |
    grep -v "dockerd" | grep -v "containerd" |
    grep -v "/usr/lib/gnupg/scdaemon"
)
echo "################################################################################"
if [ "${BOOT_ERRORS}" == "" ]; then
  echo "No Boot errors, yay!"
else
  echo "Boot errors encountered, boo!"
  echo "################################################################################"
  echo "${BOOT_ERRORS}"
fi
echo "################################################################################" || [ "${BOOT_ERRORS}" == "" ]