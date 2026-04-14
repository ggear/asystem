#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

media-truncate
media-refresh
media-normalise
media-clean
media-analyse
media-space
