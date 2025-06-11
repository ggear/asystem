#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

asystem-media-normalise
asystem-media-analyse
asystem-media-rename
asystem-media-merge
asystem-media-check
asystem-media-upscale
asystem-media-refresh
asystem-media-analyse
asystem-media-space
