#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

. ./.env

if [ $(ffprobe 2>/dev/null | grep "${MEDIA_FFMPEG_VERSION}" | wc -l) -ne 1 ]; then
  cd /usr/local/lib
  [[ -d "./ffmpeg" ]] && git clone git://git.videolan.org/ffmpeg.git
  cd ffmpeg
  git checkout n${MEDIA_FFMPEG_VERSION}
  ./configure --prefix=/usr
  make -j 8
  for BIN in "ffmpeg" "ffprobe"; do
    rm /usr/bin/${BIN}
    ln -s /usr/local/lib/ffmpeg/${BIN} /usr/bin/${BIN}
  done
fi

cd ${SERVICE_INSTALL} || exit

for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  mkdir -p ${SHARE_DIR}/tmp/scripts
  for SHARE_DIR_SCOPE in "kids" "parents" "docos" "comedy"; do
    for SHARE_DIR_TYPE in "audio" "movies" "series"; do
      mkdir -p ${SHARE_DIR}/media/${SHARE_DIR_SCOPE}/${SHARE_DIR_TYPE}
    done
  done
done

for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  for SHARE_DIR_SCOPE in "kids" "docos" "comedy"; do
    for SHARE_DIR_TYPE in "movies" "series"; do
      cat <<EOF >"${SHARE_DIR}/media/${SHARE_DIR_SCOPE}/${SHARE_DIR_TYPE}/._defaults.yaml"
- target_quality: Min
EOF
    done
  done
  cat <<EOF >"${SHARE_DIR}/media/parents/movies/._defaults.yaml"
- target_quality: Mid
- target_channels: '5'
EOF
  cat <<EOF >"${SHARE_DIR}/media/parents/series/._defaults.yaml"
- target_quality: Min
EOF
done

if [ ! -d /root/.pyenv/versions/${PYTHON_VERSION}/bin ]; then
  pyenv install ${PYTHON_VERSION}
fi
/root/.pyenv/versions/${PYTHON_VERSION}/bin/pip install -r config/.reqs.txt

cp -rvf /var/lib/asystem/install/media/latest/config/bin/lib/other-transcode.rb /usr/local/bin/other-transcode
chmod +x /usr/local/bin/other-transcode

mkdir -p /root/.config
cp -rvf /var/lib/asystem/install/media/latest/config/.gspread_pandas /root/.config/gspread_pandas

chmod +x config/bin/*.sh config/bin/lib/*.sh
for SCRIPT in /var/lib/asystem/install/media/latest/config/bin/*.sh; do
  rm -rf /usr/local/bin/asystem-$(basename ${SCRIPT} .sh)
  ln -vs ${SCRIPT} /usr/local/bin/asystem-$(basename ${SCRIPT} .sh)
done
