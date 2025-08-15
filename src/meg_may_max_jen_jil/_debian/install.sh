#!/bin/bash

################################################################################
# Packages upgrade
################################################################################
cd /tmp
apt-get clean
apt-get update

################################################################################
# Packages install
################################################################################
apt-get -y --allow-downgrades install jq=1.6-2.1
apt-get -y --allow-downgrades install yq=3.1.0-3
apt-get -y --allow-downgrades install xq=1.0.0-2+b5
apt-get -y --allow-downgrades install duf=0.8.1-1+b6
apt-get -y --allow-downgrades install ntp=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1+deb12u1
apt-get -y --allow-downgrades install psmisc=23.6-1
apt-get -y --allow-downgrades install usbutils=1:014-1+deb12u1
apt-get -y --allow-downgrades install dnsutils=1:9.18.33-1~deb12u2
apt-get -y --allow-downgrades install ntpdate=1:4.2.8p15+dfsg-2~1.2.2+dfsg1-1+deb12u1
apt-get -y --allow-downgrades install ntfs-3g=1:2022.10.3-1+deb12u2
apt-get -y --allow-downgrades install ifupdown=0.8.41
apt-get -y --allow-downgrades install nvme-cli=2.4+really2.3-3
apt-get -y --allow-downgrades install acl=2.3.1-3
apt-get -y --allow-downgrades install unrar=1:6.2.6-1+deb12u1
apt-get -y --allow-downgrades install rsync=3.2.7-1+deb12u2
apt-get -y --allow-downgrades install vim=2:9.0.1378-2+deb12u2
apt-get -y --allow-downgrades install rename=2.01-1
apt-get -y --allow-downgrades install parted=3.5-3
apt-get -y --allow-downgrades install curl=7.88.1-10+deb12u12
apt-get -y --allow-downgrades install screen=4.9.0-4
apt-get -y --allow-downgrades install fswatch=1.14.0+repack-13.1+b1
apt-get -y --allow-downgrades install util-linux=2.38.1-5+deb12u3
apt-get -y --allow-downgrades install mediainfo=23.04-1
apt-get -y --allow-downgrades install digitemp=3.7.2-2
apt-get -y --allow-downgrades install tuptime=5.2.2
apt-get -y --allow-downgrades install bsdmainutils=12.1.8
apt-get -y --allow-downgrades install netselect-apt=0.3.ds1-30.1
apt-get -y --allow-downgrades install smartmontools=7.3-1+b1
apt-get -y --allow-downgrades install avahi-daemon=0.8-10+deb12u1
apt-get -y --allow-downgrades install avahi-utils=0.8-10+deb12u1
apt-get -y --allow-downgrades install net-tools=2.10-0.1+deb12u2
apt-get -y --allow-downgrades install ethtool=1:6.1-1
apt-get -y --allow-downgrades install lm-sensors=1:3.6.0-7.1
apt-get -y --allow-downgrades install efivar=37-6
apt-get -y --allow-downgrades install apt-transport-https=2.6.1
apt-get -y --allow-downgrades install ca-certificates=20230311+deb12u1
apt-get -y --allow-downgrades install gnupg-agent=2.2.40-1.1
apt-get -y --allow-downgrades install bash-completion=1:2.11-6
apt-get -y --allow-downgrades install software-properties-common=0.99.30-4.1~deb12u1
apt-get -y --allow-downgrades install mkvtoolnix=74.0.0-1
apt-get -y --allow-downgrades install docker-ce=5:28.3.3-1~debian.12~bookworm
apt-get -y --allow-downgrades install docker-ce-cli=5:28.3.3-1~debian.12~bookworm
apt-get -y --allow-downgrades install containerd.io=1.7.27-1
apt-get -y --allow-downgrades install cifs-utils=2:7.0-2
apt-get -y --allow-downgrades install samba=2:4.17.12+dfsg-0+deb12u2
apt-get -y --allow-downgrades install cups=2.4.2-3+deb12u8
apt-get -y --allow-downgrades install smbclient=2:4.17.12+dfsg-0+deb12u2
apt-get -y --allow-downgrades install inotify-tools=3.22.6.0-4
apt-get -y --allow-downgrades install htop=3.2.2-2
apt-get -y --allow-downgrades install iotop=0.6-42-ga14256a-0.1+b2
apt-get -y --allow-downgrades install hdparm=9.65+ds-1
apt-get -y --allow-downgrades install bolt=0.9.5-1
apt-get -y --allow-downgrades install stress-ng=0.15.06-2
apt-get -y --allow-downgrades install memtester=4.6.0-1
apt-get -y --allow-downgrades install linux-cpupower=6.1.140-1
apt-get -y --allow-downgrades install firmware-linux-nonfree=20230210-5
apt-get -y --allow-downgrades install hwinfo=21.82-1
apt-get -y --allow-downgrades install lshw=02.19.git.2021.06.19.996aaad9c7-2+b1
apt-get -y --allow-downgrades install vlan=2.0.5
apt-get -y --allow-downgrades install powertop=2.14-1+b2
apt-get -y --allow-downgrades install locales=2.36-9+deb12u10
apt-get -y --allow-downgrades install python3=3.11.2-1+b1
apt-get -y --allow-downgrades install python3-pip=23.0.1+dfsg-1
apt-get -y --allow-downgrades install tesseract-ocr=5.3.0-2
apt-get -y --allow-downgrades install libedgetpu1-std=16.0
apt-get -y --allow-downgrades install exfatprogs=1.2.0-1+deb12u1
apt-get -y --allow-downgrades install build-essential=12.9
apt-get -y --allow-downgrades install automake=1:1.16.5-1.3
apt-get -y --allow-downgrades install autoconf=2.71-3
apt-get -y --allow-downgrades install checkinstall=1.6.2+git20170426.d24a630-3+b1
apt-get -y --allow-downgrades install libtool=2.4.7-7~deb12u1
apt-get -y --allow-downgrades install pkg-config=1.8.1-1
apt-get -y --allow-downgrades install intltool=0.51.0-6
apt-get -y --allow-downgrades install yasm=1.3.0-4
apt-get -y --allow-downgrades install nasm=2.16.01-1
apt-get -y --allow-downgrades install ruby-full=1:3.1
apt-get -y --allow-downgrades install xz-utils=5.4.1-1
apt-get -y --allow-downgrades install tk-dev=8.6.13
apt-get -y --allow-downgrades install zlib1g-dev=1:1.2.13.dfsg-1
apt-get -y --allow-downgrades install llvm=1:14.0-55.7~deb12u1
apt-get -y --allow-downgrades install libssl-dev=3.0.17-1~deb12u1
apt-get -y --allow-downgrades install libbz2-dev=1.0.8-5+b1
apt-get -y --allow-downgrades install libreadline-dev=8.2-1.3
apt-get -y --allow-downgrades install libsqlite3-dev=3.40.1-2+deb12u1
apt-get -y --allow-downgrades install libncurses5-dev=6.4-4
apt-get -y --allow-downgrades install libncursesw5-dev=6.4-4
apt-get -y --allow-downgrades install libffi-dev=3.4.4-1
apt-get -y --allow-downgrades install liblzma-dev=5.4.1-1
apt-get -y --allow-downgrades install libxml2-dev=2.9.14+dfsg-1.3~deb12u2
apt-get -y --allow-downgrades install libgtk2.0-dev=2.24.33-2+deb12u1
apt-get -y --allow-downgrades install libnotify-dev=0.8.1-1
apt-get -y --allow-downgrades install libglib2.0-dev=2.74.6-2+deb12u6
apt-get -y --allow-downgrades install libevent-dev=2.1.12-stable-8
apt-get -y --allow-downgrades install libcurl4-openssl-dev=7.88.1-10+deb12u12

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
sed -i -E '/^#|^$/!{/en_AU.UTF-8 UTF-8/!s/^/#/}' /etc/locale.gen
locale-gen en_AU.UTF-8
echo "LANG=en_AU.UTF-8" >/etc/default/locale
update-locale LANG=en_AU.UTF-8
locale

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
# Network
################################################################################
mkdir -p /etc/network
INTERFACE=$(lshw -C network -short -c network 2>/dev/null | grep -i ethernet | tr -s ' ' | cut -d' ' -f2 | grep -v 'path\|=\|network')
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "auto eth0." /etc/network/interfaces | wc -l) -eq 0 ]; then
  MACADDRESS_SUFFIX="$(ifconfig "${INTERFACE}" | grep ether | tr -s ' ' | cut -d' ' -f3 | cut -d':' -f2-)"
  if [ "${INTERFACE}" != "" ]; then
    cat <<EOF >/etc/network/interfaces
# interfaces(5) file used by ifup(8) and ifdown(8)
# Include files from /etc/network/interfaces.d:

source /etc/network/interfaces.d/*

rename ${INTERFACE}=eth0

auto eth0
iface eth0 inet dhcp

#auto eth0.3
#iface eth0.3 inet dhcp
#    vlan-raw-device eth0
#    pre-up ip link set eth0.3 address 3a:${MACADDRESS_SUFFIX}
#
#auto eth0.4
#iface eth0.4 inet dhcp
#    vlan-raw-device eth0
#    pre-up ip link set eth0.4 address 4a:${MACADDRESS_SUFFIX}

EOF
  fi
fi
systemctl start networking
systemctl enable networking
systemctl status networking
systemctl stop NetworkManager
systemctl disable NetworkManager
systemctl mask NetworkManager
systemctl stop ModemManager
systemctl disable ModemManager
systemctl mask ModemManager
systemctl stop systemd-networkd
systemctl disable systemd-networkd
systemctl mask systemd-networkd
systemctl stop wpa_supplicant
systemctl disable wpa_supplicant
systemctl mask wpa_supplicant
grep -q '^8021q' /etc/modules 2>/dev/null || echo '8021q' | tee -a /etc/modules
grep -q '^macvlan' /etc/modules 2>/dev/null || echo 'macvlan' | tee -a /etc/modules
grep -q '^blacklist applesmc' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist applesmc' | tee -a /etc/modprobe.d/blacklist-applesmc.conf
grep -q '^blacklist bcma-pci-bridge' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist bcma-pci-bridge' | tee -a /etc/modprobe.d/blacklist-wifi.conf

################################################################################
# Power
################################################################################
cat <<'EOF' >/etc/systemd/system/powertop.service
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
systemctl enable powertop
# INFO: Warning, this is aggressive and overides the below keyboard udev rule such the keyboard goes to sleep all the time, annoying!
#systemctl stop powertop
#systemctl disable powertop

################################################################################
# Keyboard
################################################################################
echo 'ACTION=="add", SUBSYSTEM=="usb", KERNEL=="1-1.4.1", ATTR{idVendor}=="04d9", ATTR{idProduct}=="0006", ATTR{power/control}="on"' | tee /etc/udev/rules.d/99-holtek-keyboard.rules >/dev/null
udevadm control --reload
udevadm trigger

################################################################################
# Bluetooth
################################################################################
systemctl stop bluetooth.service
systemctl disable bluetooth.service
systemctl mask bluetooth.service
grep -q '^blacklist bluetooth' /etc/modprobe.d/blacklist-bluetooth.conf 2>/dev/null || echo 'blacklist bluetooth' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf

################################################################################
# Sound
################################################################################
BLACKLIST_FILE="/etc/modprobe.d/alsa-blacklist.conf"
MODULES=(
  snd_bcm2835
  snd_pcm
  snd_seq
  snd_timer
  snd
  snd_soc_core
  snd_seq_device
  snd_pcm_oss
  snd_mixer_oss
)
[ ! -f "$BLACKLIST_FILE" ] && touch "$BLACKLIST_FILE"
for mod in "${MODULES[@]}"; do
  grep -qx "$mod" "$BLACKLIST_FILE" || echo "blacklist $mod" | tee -a "$BLACKLIST_FILE" >/dev/null
done
systemctl mask alsa-utils.service alsa-restore.service alsa-state.service

################################################################################
# USB
################################################################################
echo "USB block devices"
lsblk -o NAME,SIZE,TRAN -nr | grep usb | while read dev size tran; do
  for part in $(lsblk -ln -o NAME /dev/$dev | tail -n +2); do
    mp=$(findmnt -nr -S /dev/$part -o TARGET)
    [ -z "$mp" ] && continue
    speed=$(lsusb -t | grep -Eo '5000M|480M|12M' | head -n1)
    case $speed in
    5000M) speed_h="USB 3.0 (5 Gbps)" ;;
    480M) speed_h="USB 2.0 (480 Mbps)" ;;
    12M) speed_h="USB 1.1 (12 Mbps)" ;;
    *) speed_h="Unknown" ;;
    esac
    echo "  - /dev/$part ($size) mounted at $mp, speed: $speed_h"
  done
done

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
git checkout v2.6.5
./src/configure && make -C src
source /root/.bashrc
cd /tmp

################################################################################
# Temperature
################################################################################
sensors-detect --auto

################################################################################
# Printing
################################################################################
systemctl stop cups
systemctl disable cups
systemctl mask cups

################################################################################
# Docker
################################################################################
[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q) 2>/dev/null
docker system prune --volumes -f 2>/dev/null
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

################################################################################
# Uptime
################################################################################
tuptime

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
    grep -v "Temporary failure in name resolution"
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
