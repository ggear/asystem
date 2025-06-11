#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

asystem-media-analyse
asystem-media-rename
asystem-media-merge
asystem-media-check
asystem-media-upscale
asystem-media-refresh
asystem-media-analyse
