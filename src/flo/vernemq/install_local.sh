#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

${ROOT_DIR}/deploy.sh
