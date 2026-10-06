#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

replace_path "${ROOT_DIR}/src/main/python/.py_deps.txt" "${ROOT_DIR}/src/main/resources/.reqs.txt" || exit $?
for FILE in "stage.py" "analyse.py" "refresh.py"; do
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" >"${ROOT_DIR}/src/main/resources/bin/lib/${FILE}" || exit 1
  cat "${ROOT_DIR}/src/main/python/media/${FILE}" >>"${ROOT_DIR}/src/main/resources/bin/lib/${FILE}" || exit $?
done

# NOTES: https://github.com/lisamelton/other_video_transcoding/releases
VERSION=2025.01.21
pull_repo "${ROOT_DIR}" "${1}" "media" "other_video_transcoding" "ggear/other_video_transcoding" "ggear-tested" "https://github.com/lisamelton/other_video_transcoding.git" "${VERSION}" || exit $?
replace_path "${ROOT_DIR}/../../../.deps/media/other_video_transcoding/other-transcode.rb" "${ROOT_DIR}/src/main/resources/bin/lib/other-transcode.rb" || exit $?
replace_path "${ROOT_DIR}/src/main/resources/bin/lib/other-transcode.rb" "/usr/local/bin/other-transcode" || exit $?
chmod +x "/usr/local/bin/other-transcode" || exit $?
