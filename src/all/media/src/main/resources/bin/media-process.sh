#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

RESULT=0
media-normalise || RESULT=1
media-analyse || RESULT=1
media-rename || RESULT=1
media-check || RESULT=1
media-upscale || RESULT=1
media-reformat || RESULT=1
media-transcode || RESULT=1
media-downscale || RESULT=1
media-analyse || RESULT=1
media-space || RESULT=1
exit ${RESULT}
