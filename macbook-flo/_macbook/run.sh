#!/bin/sh

# Allow host to stay up with lid closed: https://ubuntuhandbook.org/index.php/2020/05/lid-close-behavior-ubuntu-20-04/

################################################################################
# Lid
################################################################################
sed -i 's/#HandleLidSwitch=suspend/HandleLidSwitch=ignore/g' /etc/systemd/logind.conf
sed -i 's/#HandleLidSwitchExternalPower=suspend/HandleLidSwitchExternalPower=ignore/g' /etc/systemd/logind.conf
systemctl restart systemd-logind.service

################################################################################
# Display (disabled in favour of blacklisting video drivers)
################################################################################
# Disable discrete GPU and enable integrated GPU: https://github.com/0xbb/gpu-switch, think this is the go https://github.com/0xbb/apple_set_os.efi referencing https://unix.stackexchange.com/questions/193425/enabling-intel-iris-pro-syslinux-tails-system-macbook-pro-15-retina-late-2013
#if [ -e /sys/class/backlight/gmux_backlight ] && [ ! -f /etc/systemd/system/backlight.service ]; then
#  cat <<EOF >/etc/systemd/system/backlight.service
#[Unit]
#Description=Turn backlight off
#After=default.target
#[Service]
#ExecStart=/bin/sh -c '/usr/bin/echo 0 > /sys/class/backlight/gmux_backlight/brightness'
#[Install]
#WantedBy=default.target
#EOF
#  systemctl daemon-reload
#  systemctl enable backlight.service
#  systemctl start backlight.service
#fi
#lspci -nnk | egrep -i --color 'vga|3d|2d' -A3 | grep 'in use'
#cd /tmp
#git clone git@github.com:0xbb/apple_set_os.efi.git
#cd apple_set_os.efi.git
#docker build -t apple_set_os . && docker run --rm -it -v $(pwd):/build apple_set_os
#mkdir /boot/efi/EFI/custom
#cp apple_set_os.efi /boot/efi/EFI/custom
#cat <<EOF >>/etc/grub.d/40_custom
#
#search --no-floppy --set=root --label EFI
#chainloader (${root})/EFI/custom/apple_set_os.efi
#boot
#
#EOF
#grub-install
#update-grub
#cd /tmp
#rm -rvf apple_set_os.efi.git
#lspci -vnnn | grep VGA
#cd /tmp
#git clone git@github.com:0xbb/gpu-switch.git
#cd gpu-switch
#./gpu-switch -d
