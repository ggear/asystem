#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

. ./.env

for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
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
- target_quality: Low
EOF
    done
  done
  cat <<EOF >"${SHARE_DIR}/media/parents/movies/._defaults.yaml"
- target_quality: High
EOF
  cat <<EOF >"${SHARE_DIR}/media/parents/series/._defaults.yaml"
- target_quality: Medium
EOF
done

if [ ! -d /root/.pyenv/versions/${PYTHON_VERSION}/bin ]; then
  pyenv install ${PYTHON_VERSION}
fi
/root/.pyenv/versions/${PYTHON_VERSION}/bin/pip install -r config/.reqs.txt

mkdir -p /root/.config
cp -rvf /var/lib/asystem/install/media/latest/config/.gspread_pandas /root/.config/gspread_pandas

chmod +x config/bin/*.sh config/bin/lib/*.sh
for SCRIPT in /var/lib/asystem/install/media/latest/config/bin/*.sh; do
  rm -rf /usr/bin/asystem-$(basename ${SCRIPT} .sh)
  ln -vs ${SCRIPT} /usr/bin/asystem-$(basename ${SCRIPT} .sh)
done
