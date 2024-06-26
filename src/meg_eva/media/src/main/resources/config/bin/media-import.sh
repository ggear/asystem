#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

${ROOT_DIR}/bin/lib/import.sh /share/2/tmp
