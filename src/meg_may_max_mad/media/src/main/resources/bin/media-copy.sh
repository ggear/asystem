#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

# TODO
# rsync -avhPr /share/3/media/kids /share/2/media
