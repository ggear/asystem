#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

find /share -name "reformat.sh" -type f -delete
find /share -name "transcode.sh" -type f -delete
find /share -name "._metadata_*.yaml" -type f -delete
find /share -name "._transcode_*" -type d -exec rm -r "{}" +
${PYTHON_DIR}/python ${ROOT_DIR}/lib/analyse.py /share "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8" --clean
