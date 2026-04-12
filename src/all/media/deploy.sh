#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

asystem-media-truncate
asystem-media-refresh
asystem-media-normalise
asystem-media-clean
asystem-media-analyse
asystem-media-space
