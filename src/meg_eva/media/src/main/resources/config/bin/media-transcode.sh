#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

find . -name transcode.sh
#for SHARE_DIR in ${SHARE_DIRS}; do ${PYTHON_DIR}/python --version && echo $SHARE_DIR; done


# outside of /share or inside /share - $SHARES/tmp/script/transcode.sh
# inside /share/idx - tmp/script/transcode.sh
# inside /share/idx/media - find transcode.sh
