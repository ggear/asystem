#!/bin/bash

################################################################################
# Image
################################################################################
# Type
FEDORA_ARCH="x86_64"
FEDORA_FORMAT="iso"
#FEDORA_ARCH="aarch64"
#FEDORA_FORMAT="raw.xz"
# Versions
#FEDORA_VERSION="42-1.1"
#FEDORA_IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/42/Server/x86_64/iso/Fedora-Server-netinst-${FEDORA_ARCH}-${FEDORA_VERSION}.${FEDORA_FORMAT}"
FEDORA_VERSION="latest"
FEDORA_IMAGE_URL="$(curl -s https://fedoraproject.org/releases.json | jq -r --arg arch "$FEDORA_ARCH" --arg format "$FEDORA_FORMAT" '
    map(select(
      .arch == $arch
      and .variant == "Server"
      and (.version | test("Beta") | not)
      and (.link | test($format))
    ))
    | sort_by(.version | tonumber)
    | last
    | .link // "No stable release found"
')"
# Files
FEDORA_IMAGE_FILE="/Users/graham/Desktop/fedora-${FEDORA_ARCH}-${FEDORA_VERSION}.${FEDORA_FORMAT}"
wget "${FEDORA_IMAGE_URL}" -O "${FEDORA_IMAGE_FILE}"
# Write
USB_DEV="/dev/disk4"
diskutil list
diskutil list "${USB_DEV}"
[[ $(diskutil list "${USB_DEV}" | grep 'external' | wc -l) -eq 1 ]] && diskutil unmountDisk force "${USB_DEV}"
[[ $(diskutil list "${USB_DEV}" | grep 'external' | wc -l) -eq 1 ]] && sudo dd "if=${FEDORA_IMAGE_FILE}" bs=4m | pv "${FEDORA_IMAGE_FILE}" | sudo dd "of=${USB_DEV}" bs=4m

################################################################################
# Install
################################################################################
# Language -> English UK
# Network & Host Name -> Host Name: ${HOST_TYPE}-${HOST_NAME}
# Installation Destination -> Custom -> LVM add automatic partitions, the adjust size of '/' then add '/home', '/var', '/tmp', all as ext4
# Software Selection -> Headless Management, System Tools
# Time and Date -> Australia / Perth, Automatic
# Root Account -> Enable, Allow SSH login
# User Creation -> Graham Gear, graham

################################################################################
# SSH
################################################################################
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

################################################################################
# Packages
################################################################################
# Copy install_upgrade.sh to shell and run
# Copy install.sh apt-get install commands to shell and run

################################################################################
# Btrfs
################################################################################
if mount | grep -q 'type btrfs'; then
  btrfs subvolume list /
  btrfs quota enable /
  btrfs qgroup show /
  btrfs qgroup show -pcref /var
  btrfs qgroup limit 30G /var
  btrfs qgroup show -pcref /home
  btrfs qgroup limit 335G /home
fi

################################################################################
# LVM
################################################################################
SHARE_GUID="share_05"
SHARE_SIZE="3.1TB"
if [ -n "${SHARE_GUID}" ] && [ -n "${SHARE_SIZE}" ]; then
  vgdisplay
  if ! lvdisplay /dev/$(hostname)-vg/${SHARE_GUID} >/dev/null 2>&1; then
    lvcreate -L ${SHARE_SIZE} -n ${SHARE_GUID} $(hostname)-vg
    mkfs.ext4 -m 0 -T largefile4 /dev/$(hostname)-vg/${SHARE_GUID}
  fi
  lvdisplay /dev/$(hostname)-vg/${SHARE_GUID}
  lvextend -L ${SHARE_SIZE} /dev/$(hostname)-vg/${SHARE_GUID}
  resize2fs /dev/$(hostname)-vg/${SHARE_GUID}
  tune2fs -m 0 /dev/$(hostname)-vg/${SHARE_GUID}
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Block size:'
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Block count:'
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Reserved block count:'
  lvdisplay /dev/$(hostname)-vg/${SHARE_GUID}
fi
vgdisplay | grep 'Free  PE / Size'
lvdisplay | grep 'LV Size'

################################################################################
# Shares
################################################################################
DRIVE_GUID="share_11"
dev_recent=$(ls -lt --time-style=full-iso /dev/disk/by-id/ | grep usb | sort -k6,7 -r | head -n 1 | awk '{print $NF}')
if [ -n "${dev_recent}" ]; then
  dev_path="/dev/$(lsblk -no $(echo "${dev_recent}" | grep -q '[0-9]$' && echo 'pk')name "$(readlink -f /dev/disk/by-id/"${dev_recent}")" | head -n 1)"
  dev_name=$(basename "${dev_path}")
  echo "" && lsblk -o NAME,KNAME,TRAN,SIZE,MOUNTPOINT,MODEL,SERIAL,VENDOR && echo ""
  if [ -b "${dev_path}" ]; then
    echo "" && lsblk -o NAME,KNAME,TRAN,SIZE,MOUNTPOINT,MODEL,SERIAL,VENDOR "${dev_path}" && echo ""
    dmesg | grep "${dev_name}" | tail -n 10
    echo "" && echo ""
    echo "################################################################################"
    echo "Found USB block device: ${dev_path}"
    echo "################################################################################"
    echo ""
  else
    echo "Resolved device is not a block device: ${dev_path}"
  fi
else
  echo "No USB block devices found in /dev/disk/by-id/"
fi
if [ -n "${DRIVE_GUID}" ]; then
  if [ -n "${dev_path}" ]; then
    echo "" && echo "" && fdisk -l "${dev_path}"
  fi
fi
if [ -n "${DRIVE_GUID}" ]; then
  if [ -n "${dev_path}" ]; then
    parted --script "${dev_path}" \
      mklabel gpt \
      mkpart primary 0% 100%
    parted "${dev_path}" name 1 ${DRIVE_GUID}
    echo "" && echo "" && fdisk -l "${dev_path}"
    blkid "${dev_path}"1
    if [[ "${DRIVE_GUID}" == backup* ]]; then
      mkfs.ext4 -m 0 -O dir_index,extent,^has_journal -E nodiscard "${dev_path}1"
    elif [[ "${DRIVE_GUID}" == share* ]]; then
      mkfs.ext4 -m 0 -O fast_commit,dir_index,extent,^has_journal -E nodiscard "${dev_path}1"
    else
      echo "Unknown drive GUID [${DRIVE_GUID}]"
    fi
    tune2fs -O ^has_journal "${dev_path}"1
    fsck.ext4 -f "${dev_path}"1
    tune2fs -O dir_index,extent,fast_commit "${dev_path}"1
    tune2fs -m 0 "${dev_path}"1
  fi
fi

################################################################################
# macOS
################################################################################
# About -> Name -> $HOSTNAME
# Sharing -> Remote Login
# Apple ID -> iCloud -> <ALL OFF>
setopt NULL_GLOB
defaults write com.apple.Siri SuggestionsEnabled -bool false
defaults write com.apple.Siri RecentSuggestionsEnabled -bool false
defaults write com.apple.Spotlight SuggestionsEnabled -bool false
defaults write com.apple.Spotlight SuggestionsShowInLookup -bool false
killall suggestd
keep_apps="CleanMyMac X.app"
cleanup_folder() {
  local folder="$1"
  if [ -d "${folder}" ]; then
    find "$folder" -maxdepth 1 -type d -name "*.app" | while read -r app; do
      name=$(basename "$app")
      keep=false
      for k in $keep_apps; do
        if [[ "$name" == "$k" ]]; then
          keep=true
          break
        fi
      done
      if [ "$keep" = false ]; then
        sudo rm -rf "$app" 2>/dev/null
      fi
    done
  fi
}
cleanup_folder "/Applications"
cleanup_folder "$HOME/Applications"
sudo rm -rf ~/Library/Caches/* ~/Downloads/* /tmp/* /private/var/folders/* 2>/dev/null
sudo rm -rf ~/Library/iTunes/iPhone\ Software\ Updates/* ~/Library/Application\ Support/MobileSync/Backup/* 2>/dev/null
sudo find ~/Applications -type d -name "*.lproj" ! -name "en.lproj" -exec rm -rf {} + 2>/dev/null
sudo rm -rf ~/Library/Fonts/* 2>/dev/null
sudo rm -rf ~/Library/Logs/* 2>/dev/null
sudo rm -rf /private/var/log/* 2>/dev/null
sudo rm -rf ~/Library/Mobile\ Documents/com~apple~CloudDocs/.DS_Store 2>/dev/null
sudo rm -rf ~/Library/Safari/LocalStorage/* ~/Library/Safari/Databases/* ~/Library/Safari/Favicon* 2>/dev/null
sudo rm -rf ~/Library/Application\ Support/Google/Chrome/Default/Cache/* ~/Library/Application\ Support/Firefox/Profiles/*/cache2/* 2>/dev/null
sudo rm -rf ~/.Trash/* /Volumes/*/.Trashes/* 2>/dev/null
sudo rm -rf ~/Library/Developer/Xcode/DerivedData/* ~/Library/Developer/Xcode/iOS\ DeviceSupport/* ~/Library/Developer/CoreSimulator/* 2>/dev/null
sudo rm -rf ~/Downloads/*.dmg ~/Downloads/*.zip ~/Downloads/*.tar.gz ~/Downloads/*.pkg 2>/dev/null
sudo rm -rf /private/var/vm/sleepimage /private/var/vm/swapfile* 2>/dev/null
sudo rm -rf ~/Library/Containers/com.apple.mail/Data/Library/Mail\ Downloads/* 2>/dev/null
sudo rm -rf ~/Library/Application\ Support/*Cache* 2>/dev/null
sudo rm -rf ~/Library/Application\ Support/Steam/steamapps/downloading/* 2>/dev/null
sudo rm -rf ~/Library/Application\ Support/Discord/Cache/* 2>/dev/null
sudo rm -rf ~/Library/Caches/com.apple.FontRegistry/* 2>/dev/null
sudo rm -rf ~/Library/Caches/com.apple.QuickLook.thumbnailcache/* 2>/dev/null
sudo rm -rf ~/Library/Saved\ Application\ State/* 2>/dev/null
sudo rm -rf ~/Library/Speech/* 2>/dev/null
sudo rm -rf ~/Library/Caches/Homebrew/* 2>/dev/null
sudo rm -rf /Applications/iMovie.app /Applications/GarageBand.app 2>/dev/null
sudo rm -rf ~/Movies/* 2>/dev/null
sudo rm -rf /Library/Application\ Support/com.apple.idleassetsd/Customer/* 2>/dev/null
sudo rm -rf /Library/Application\ Support/com.apple.idleassetsd/AssetsV2/* 2>/dev/null
tmutil listlocalsnapshots / 2>/dev/null | while read -r snap; do
  sudo tmutil deletelocalsnapshots "$snap" 2>/dev/null
done
sudo find / \( -path "/Volumes" -prune \) -o \
  \( -type f \( -name ".*.swp" -o -name ".*.tmp" -o \( -name "*.mov" -path "*idleassetsd*" \) \) -exec rm -v {} \; \) 2>/dev/null

################################################################################
# NIC (legacy)
################################################################################
apt-get install -y --allow-downgrades 'firmware-realtek=20210315-3'
INTERFACE=$(lshw -C network -short 2>/dev/null | grep enx | tr -s ' ' | cut -d' ' -f2)
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "${INTERFACE}" /etc/network/interfaces | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/network/interfaces

rename ${INTERFACE}=lan0
allow-hotplug lan0
iface lan0 inet dhcp
    pre-up ethtool -s lan0 speed 1000 duplex full autoneg off
EOF
fi
cat <<EOF >/etc/udev/rules.d/10-usb-network-realtek.rules
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="8153", TEST=="power/autosuspend", ATTR{power/autosuspend}="-1"
EOF
chmod -x /etc/udev/rules.d/10-usb-network-realtek.rules
echo "Power management disabled for: "$(find -L /sys/bus/usb/devices/*/power/autosuspend -exec echo -n {}": " \; -exec cat {} \; | grep ": \-1")
