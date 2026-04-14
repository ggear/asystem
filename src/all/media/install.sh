#!/bin/bash

SERVICE_HOME="/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"
SERVICE_INSTALL="/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}"

cd "${SERVICE_INSTALL}" || exit

source "./.env"

if [[ "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  if ! command -v ffprobe >/dev/null 2>&1 || [ $(ffprobe 2>&1 | grep "${MEDIA_FFMPEG_VERSION}" | wc -l) -eq 0 ]; then
    [[ ! -d "/usr/local/lib/ffmpeg" ]] && git clone git://git.videolan.org/ffmpeg.git "/usr/local/lib/ffmpeg"
    (
      cd "/usr/local/lib/ffmpeg" || exit 1
      git checkout master
      git pull --all
      git checkout "n${MEDIA_FFMPEG_VERSION}"
      ./configure --prefix="/usr" --enable-gpl --enable-libx265
      make -j 8
      for BIN in "ffmpeg" "ffprobe"; do
        rm "/usr/bin/${BIN}"
        ln -s "/usr/local/lib/ffmpeg/${BIN}" "/usr/bin/${BIN}"
      done
    )
  fi
  for SHARE_DIR in $(grep -v '^#' "/etc/fstab" | grep '/share' | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
    mkdir -p "${SHARE_DIR}/tmp/scripts"
    for SHARE_DIR_SCOPE in "kids" "parents" "docos" "comedy"; do
      for SHARE_DIR_TYPE in "audio" "movies" "series"; do
        mkdir -p "${SHARE_DIR}/media/${SHARE_DIR_SCOPE}/${SHARE_DIR_TYPE}"
      done
    done
  done
  for SHARE_DIR in $(grep -v '^#' "/etc/fstab" | grep '/share' | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
    for SHARE_DIR_SCOPE in "kids" "docos" "comedy"; do
      for SHARE_DIR_TYPE in "movies" "series"; do
        cat <<EOF >"${SHARE_DIR}/media/${SHARE_DIR_SCOPE}/${SHARE_DIR_TYPE}/._defaults.yaml"
- target_quality: 4
EOF
      done
    done
    cat <<EOF >"${SHARE_DIR}/media/parents/movies/._defaults.yaml"
- target_quality: 6
- target_channels: 5
EOF
    cat <<EOF >"${SHARE_DIR}/media/parents/series/._defaults.yaml"
- target_quality: 4
EOF
  done
fi
if [ ! -d "${HOME}/.pyenv/versions/${ASYSTEM_PYTHON_VERSION}/bin" ]; then
  pyenv install "${ASYSTEM_PYTHON_VERSION}"
  "${HOME}/.pyenv/versions/${ASYSTEM_PYTHON_VERSION}/bin/pip" install --root-user-action ignore --default-timeout=1000 --upgrade pip
  "${HOME}/.pyenv/versions/${ASYSTEM_PYTHON_VERSION}/bin/pip" install --root-user-action ignore --default-timeout=1000 -r "./.reqs.txt"
fi
cp -rvf "/var/lib/asystem/install/media/latest/bin/lib/other-transcode.rb" "/usr/local/bin/other-transcode"
chmod +x "/usr/local/bin/other-transcode"
mkdir -p "${HOME}/.config"
cp -rvf "/var/lib/asystem/install/media/latest/.gspread_pandas" "${HOME}/.config/gspread_pandas"
chmod +x "/var/lib/asystem/install/media/latest/bin/"*.sh "/var/lib/asystem/install/media/latest/bin/lib/"*.sh
for SCRIPT in "/var/lib/asystem/install/media/latest/bin/"*.sh; do
  rm -rf "/usr/local/bin/asystem-$(basename "${SCRIPT}" .sh)"
  rm -rf "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
  ln -vs "${SCRIPT}" "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
done
