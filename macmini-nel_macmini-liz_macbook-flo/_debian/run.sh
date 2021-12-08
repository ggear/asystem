#!/bin/bash

################################################################################
# Packages (from update script)
################################################################################
apt-get update
apt-get install -y --allow-downgrades ntp=1:4.2.8p15+dfsg-1
apt-get install -y --allow-downgrades ntfs-3g=1:2017.3.23AR.3-4+deb11u1
apt-get install -y --allow-downgrades acl=2.2.53-10
apt-get install -y --allow-downgrades unrar=1:6.0.3-1
apt-get install -y --allow-downgrades rsync=3.2.3-4+deb11u1
apt-get install -y --allow-downgrades vim=2:8.2.2434-3
apt-get install -y --allow-downgrades rename=1.13-1
apt-get install -y --allow-downgrades curl=7.74.0-1.3+b1
apt-get install -y --allow-downgrades screen=4.8.0-6
apt-get install -y --allow-downgrades fswatch=1.14.0+repack-13
apt-get install -y --allow-downgrades netselect-apt=0.3.ds1-29
apt-get install -y --allow-downgrades smartmontools=7.2-1
apt-get install -y --allow-downgrades avahi-daemon=0.8-5
apt-get install -y --allow-downgrades net-tools=1.60+git20181103.0eebece-1
apt-get install -y --allow-downgrades mbpfan=2.2.1-1
apt-get install -y --allow-downgrades lm-sensors=1:3.6.0-7
apt-get install -y --allow-downgrades apt-transport-https=2.2.4
apt-get install -y --allow-downgrades ca-certificates=20210119
apt-get install -y --allow-downgrades gnupg-agent=2.2.27-2
apt-get install -y --allow-downgrades software-properties-common=0.96.20.2-2.1
apt-get install -y --allow-downgrades docker-ce=5:20.10.11~3-0~debian-bullseye
apt-get install -y --allow-downgrades docker-ce-cli=5:20.10.11~3-0~debian-bullseye
apt-get install -y --allow-downgrades containerd.io=1.4.12-1
apt-get install -y --allow-downgrades cifs-utils=2:6.11-3.1
apt-get install -y --allow-downgrades samba=2:4.13.13+dfsg-1~deb11u2
apt-get install -y --allow-downgrades cups=2.3.3op2-3+deb11u1
apt-get install -y --allow-downgrades smbclient=2:4.13.13+dfsg-1~deb11u2
apt-get install -y --allow-downgrades inotify-tools=3.14-8.1
apt-get install -y --allow-downgrades htop=3.0.5-7
apt-get install -y --allow-downgrades iotop=0.6-24-g733f3f8-1.1
apt-get install -y --allow-downgrades hdparm=9.60+ds-1
apt-get install -y --allow-downgrades stress-ng=0.12.06-1
apt-get install -y --allow-downgrades memtester=4.5.0-1
apt-get install -y --allow-downgrades linux-cpupower=5.10.70-1
apt-get install -y --allow-downgrades firmware-realtek=20210315-3
apt-get install -y --allow-downgrades firmware-linux-nonfree=20210315-3
apt-get install -y --allow-downgrades hwinfo=21.72-1
apt-get install -y --allow-downgrades lshw=02.18.85-0.7
apt-get install -y --allow-downgrades powertop=2.11-1
apt-get install -y --allow-downgrades libc6-i386=2.31-13+deb11u2
apt-get install -y --allow-downgrades intel-microcode=3.20210608.2

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
chown -R graham.graham /home/graham/.config
mkdir -p /root/.config/htop && rm -rf /root/.config/htop/htoprc
ln -s /home/graham/.config/htop/htoprc /root/.config/htop/htoprc

################################################################################
# Utilities
################################################################################
if [ ! -d /usr/local/go ]; then
  mkdir /tmp/go && cd /tmp/go
  wget -q https://dl.google.com/go/go1.14.linux-amd64.tar.gz
  tar xvfz go1.14.linux-amd64.tar.gz
  mv go /usr/local/go
  ln -s /usr/local/go/bin/go /usr/local/bin/go
  cd && rm -rf /tmp/go
fi

################################################################################
# Network
################################################################################
cat <<EOF >/etc/avahi/avahi-daemon.conf
[server]
use-ipv4=yes
use-ipv6=yes
ratelimit-interval-usec=1000000
ratelimit-burst=1000
cache-entries-max=0
[wide-area]
enable-wide-area=yes
[publish]
publish-hinfo=no
publish-workstation=no
[reflector]
enable-reflector=yes
reflect-ipv=no
[rlimits]
EOF

################################################################################
# Time
################################################################################
systemctl mask systemd-timesyncd.service
sed -i 's/0.debian.pool.ntp.org/216.239.35.0/g' /etc/ntp.conf
sed -i 's/1.debian.pool.ntp.org/216.239.35.4/g' /etc/ntp.conf
sed -i 's/2.debian.pool.ntp.org/216.239.35.8/g' /etc/ntp.conf
sed -i 's/3.debian.pool.ntp.org/216.239.35.12/g' /etc/ntp.conf
systemctl daemon-reload
systemctl restart ntp.service
systemctl status ntp.service
ntpq -p

################################################################################
# Monitoring
################################################################################
sensors-detect --auto
cat <<EOF >/etc/mbpfan.conf
[general]
min_fan_speed = 1800
max_fan_speed = 5500
low_temp = 60
high_temp = 66
max_temp = 80
polling_interval = 1
EOF
curl https://raw.githubusercontent.com/linux-on-mac/mbpfan/49f544fd8d596fa13d5525a5b042eee311568c67/mbpfan.service -o /etc/systemd/system/mbpfan.service
systemctl enable mbpfan.service

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
curl -sL "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
docker system prune --volumes -f 2>/dev/null
if [ $(grep "cdgroup_enable=memory swapaccount=1" /etc/default/grub | wc -l) -eq 0 ]; then
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
