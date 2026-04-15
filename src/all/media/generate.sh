#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

cp -rvf "${ROOT_DIR}/src/main/python/.py_deps.txt" "${ROOT_DIR}/src/main/resources/.reqs.txt"
for FILE in "ingress.py" "analyse.py"; do
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" >"${ROOT_DIR}/src/main/resources/bin/lib/${FILE}"
  cat "${ROOT_DIR}/src/main/python/media/${FILE}" >>"${ROOT_DIR}/src/main/resources/bin/lib/${FILE}"
done

# NOTES: https://github.com/lisamelton/other_video_transcoding/releases
VERSION=2025.01.21
pull_repo "${ROOT_DIR}" "${1}" "media" "other_video_transcoding" "ggear/other_video_transcoding" "ggear-tested" "https://github.com/lisamelton/other_video_transcoding.git" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/bin/lib/other-transcode.rb"
mkdir -p "${ROOT_DIR}/src/main/resources/bin/lib"
cp -rvf "${ROOT_DIR}/../../../.deps/media/other_video_transcoding/other-transcode.rb" "${ROOT_DIR}/src/main/resources/bin/lib"
cp -rvf "${ROOT_DIR}/src/main/resources/bin/lib/other-transcode.rb" "/usr/local/bin/other-transcode"
chmod +x "/usr/local/bin/other-transcode"
