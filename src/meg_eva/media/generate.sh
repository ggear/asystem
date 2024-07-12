#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/reqs_run.txt ${ROOT_DIR}/src/main/resources/config/.reqs.txt
for FILE in "rename.py" "analyse.py"; do
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" > ${ROOT_DIR}/src/main/resources/config/bin/lib/${FILE}
  cat ${ROOT_DIR}/src/main/python/media/${FILE} >> ${ROOT_DIR}/src/main/resources/config/bin/lib/${FILE}
done

VERSION=ggear-tested
pull_repo $(pwd) media other_video_transcoding ggear/other_video_transcoding ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/config/bin/lib/other-transcode.rb
mkdir -p ${ROOT_DIR}/src/main/resources/config/bin/lib &&
  cp -rvf  ${ROOT_DIR}/../../../.deps/media/other_video_transcoding/other-transcode.rb ${ROOT_DIR}/src/main/resources/config/bin/lib
cp -rvf ${ROOT_DIR}/src/main/resources/config/bin/lib/other-transcode.rb /usr/local/bin/other-transcode
chmod +x /usr/local/bin/other-transcode
