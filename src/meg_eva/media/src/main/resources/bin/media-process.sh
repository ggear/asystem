#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

asystem-media-normalise
asystem-media-analyse
asystem-media-rename
asystem-media-check
asystem-media-upscale
asystem-media-reformat
asystem-media-transcode
asystem-media-downscale
asystem-media-analyse
asystem-media-space
