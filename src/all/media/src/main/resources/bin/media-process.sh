#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

media-normalise
media-analyse
media-rename
media-check
media-upscale
media-reformat
media-transcode
media-downscale
media-analyse
media-space
